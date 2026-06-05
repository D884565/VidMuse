"""视频生成服务（调用火山引擎视频生成模型）"""
import os
import uuid
import tempfile
import logging
import math

from backend.providers import VolcanoLLM, VideoRequest
from backend.v1.app.models.frame import Frame
from backend.v1.app.generate.service.workflow.media_resolvers import resolve_video_generation_prompt
from backend.ffmpeg import ffmpeg_tool
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)


class VideoComposer:
    """视频生成服务（调用 Seedance 1.5）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self._llm = None
        self.storage = get_storage_client()

    @property
    def llm(self):
        if self._llm is None:
            if VolcanoLLM is None:
                raise RuntimeError("VolcanoLLM 不可用，请安装 openai 依赖")
            self._llm = VolcanoLLM(key=None, model_name=None)
        return self._llm

    def compose_frames(
        self,
        frames: list[Frame],
        output_dir: str,
        target_duration: float | None = None,
        *,
        allow_placeholder_segments: bool = False,
        on_segment_ready=None,
    ) -> str:
        """
        为每个 Frame 生成视频片段并拼接。

        :param frames: Frame 对象列表（需包含 image_url、prompt、duration 等）
        :param output_dir: 输出目录
        :returns: 拼接后视频的本地路径
        """
        os.makedirs(output_dir, exist_ok=True)
        self.validate_frames_for_video(frames)

        video_paths = []
        generated_segments = []
        for i, frame in enumerate(frames):
            try:
                logger.info(f"[视频生成] 开始生成帧 {frame.sequence}/{len(frames)}")

                local_path = self._generate_frame_video(frame, output_dir)

                video_paths.append(local_path)
                generated_segments.append((frame, local_path))
                if on_segment_ready:
                    on_segment_ready(frame, local_path)

                frame.status = 2  # 已完成
                frame.error_message = None
                logger.info(f"[视频生成] 帧 {frame.sequence} 生成成功: {local_path}")
            except Exception as e:
                logger.error(f"[视频生成] 帧 {frame.sequence} 生成失败: {str(e)}")
                frame.status = 3  # 失败
                frame.error_message = f"视频生成失败: {str(e)}"
                # 单帧失败不再中断整片合成，用占位片段保持时间线完整。
                placeholder_duration = max(1.0, float(frame.duration or 5))
                if not allow_placeholder_segments:
                    raise
                video_paths.append(
                    self._generate_placeholder_video(
                        output_dir,
                        int(math.ceil(placeholder_duration)),
                        i,
                        message=f"Frame {frame.sequence} video failed",
                    )
                )

        # 拼接
        if len(video_paths) > 1:
            final_path = self._concat_videos(video_paths, output_dir)
        elif video_paths:
            final_path = video_paths[0]
        else:
            final_path = self._generate_placeholder_video(output_dir, 30, 0)

        self.last_generated_segments = generated_segments
        if target_duration:
            return self._trim_final_video(final_path, output_dir, target_duration)
        return final_path

    def _generate_frame_video(self, frame: Frame, output_dir: str) -> str:
        """生成或复用单帧视频片段。"""
        existing_url = getattr(frame, "video_url", None)
        if existing_url and str(existing_url).startswith("http") and not getattr(frame, "dirty", 0):
            local_existing = os.path.join(output_dir, f"frame_{frame.sequence}_{uuid.uuid4().hex}_cached.mp4")
            try:
                self._download_video(existing_url, local_existing)
                self._validate_local_video(local_existing)
                logger.info(f"[视频复用] 帧 {frame.sequence} 使用已有视频片段")
                return local_existing
            except Exception as stale_err:
                logger.warning(f"[视频复用] 帧 {frame.sequence} 已有视频不可用，重新生成: {stale_err}")

        prompt = resolve_video_generation_prompt(frame)
        ai_params = frame.ai_params or {}
        camera = ai_params.get("camera", "")
        mood = ai_params.get("mood", "")
        if camera:
            prompt += f"\n镜头运动：{camera}"
        if mood:
            prompt += f"\n氛围：{mood}"

        generation_duration = 5
        target_dur = max(1.0, float(frame.duration or generation_duration))
        video_request = VideoRequest(
            duration=generation_duration,
            ratio="9:16",
            generate_audio=False,
            draft=False,
            watermark=False,
        )

        image_url = frame.image_url if frame.image_url and frame.image_url.startswith("http") else None
        response = self.llm.generate_video_sync(request=video_request, prompt=prompt, image=image_url)
        if not response or not response.video_url:
            raise ValueError("视频生成失败，未获取到视频 URL")

        local_path = os.path.join(output_dir, f"frame_{frame.sequence}_{uuid.uuid4().hex}.mp4")
        self._download_video(response.video_url, local_path)
        return self._fit_video_duration(local_path, output_dir, frame.sequence, target_dur)

    def _fit_video_duration(self, local_path: str, output_dir: str, sequence: int, target_dur: float) -> str:
        """把模型固定时长的视频裁剪或补足到分镜目标时长。"""
        if target_dur < 5:
            trimmed_path = os.path.join(output_dir, f"frame_{sequence}_{uuid.uuid4().hex}_trimmed.mp4")
            try:
                ffmpeg_tool.split_video(local_path, trimmed_path, start=0, end=target_dur)
                return trimmed_path
            except Exception as trim_err:
                logger.warning(f"[视频裁剪] 裁剪失败，使用原始 5 秒: {trim_err}")
                return local_path

        if target_dur > 5:
            extended_path = os.path.join(output_dir, f"frame_{sequence}_{uuid.uuid4().hex}_extended.mp4")
            try:
                ffmpeg_tool.loop_video(local_path, extended_path, target_duration=target_dur)
                return extended_path
            except Exception as extend_err:
                logger.warning(f"[视频补时] 补时失败，使用原始 5 秒: {extend_err}")
        return local_path

    def _validate_local_video(self, local_path: str) -> None:
        """轻量校验缓存视频是否存在且非空。"""
        if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
            raise RuntimeError("cached video is empty")

    def _trim_final_video(self, video_path: str, output_dir: str, target_duration: float) -> str:
        """最终成片超过目标时长时做一次总裁剪。"""
        trimmed_path = os.path.join(output_dir, f"final_{uuid.uuid4().hex}_trimmed.mp4")
        try:
            ffmpeg_tool.split_video(video_path, trimmed_path, start=0, end=float(target_duration))
            return trimmed_path
        except Exception as trim_err:
            logger.warning(f"[视频总裁剪] 裁剪失败，使用未裁剪成片: {trim_err}")
            return video_path

    def validate_frames_for_video(self, frames: list[Frame]) -> None:
        """视频生成前硬校验，避免失败帧或缺图帧继续消耗 Seedance 配额。"""
        invalid = []
        for frame in frames:
            image_url = getattr(frame, "image_url", None)
            status = getattr(frame, "status", None)
            if status == 3:
                invalid.append(f"frame {getattr(frame, 'id', None)} status == 3")
            elif not image_url or not str(image_url).startswith("http"):
                invalid.append(f"frame {getattr(frame, 'id', None)} missing image_url")
        if invalid:
            raise ValueError("video generation requires successful frame images: " + "; ".join(invalid))

    def _concat_videos(self, video_paths: list[str], output_dir: str) -> str:
        """
        使用 FFmpeg 拼接多个视频片段。

        :param video_paths: 视频片段路径列表
        :param output_dir: 输出目录
        :returns: 拼接后的视频路径
        """
        output_path = os.path.join(output_dir, f"concat_{uuid.uuid4().hex}.mp4")

        try:
            ffmpeg_tool.concat_videos(video_paths, output_path)
            logger.info(f"[视频拼接] FFmpeg concat 成功: {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"[视频拼接] FFmpeg concat 失败: {str(e)}，尝试 moviepy fallback")
            return self._concat_videos_moviepy(video_paths, output_dir)

    def _concat_videos_moviepy(self, video_paths: list[str], output_dir: str) -> str:
        """
        使用 moviepy 拼接多个视频片段（fallback 方案）。

        :param video_paths: 视频片段路径列表
        :param output_dir: 输出目录
        :returns: 拼接后的视频路径
        """
        output_path = os.path.join(output_dir, f"concat_{uuid.uuid4().hex}.mp4")

        try:
            from moviepy import VideoFileClip, concatenate_videoclips

            clips = []
            for video_path in video_paths:
                clip = VideoFileClip(video_path)
                clips.append(clip)

            # 拼接视频
            final_clip = concatenate_videoclips(clips, method="compose")
            final_clip.write_videofile(output_path, fps=24, logger=None)

            # 关闭所有 clip
            for clip in clips:
                clip.close()
            final_clip.close()

            logger.info(f"[视频拼接] moviepy concat 成功: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"[视频拼接] moviepy concat 失败: {str(e)}")
            # 如果所有拼接方式都失败，返回第一个视频
            raise RuntimeError(f"video concat failed: {e}") from e

    def _download_video(self, url: str, local_path: str):
        """
        下载视频到本地。

        :param url: 视频 URL
        :param local_path: 本地保存路径
        """
        import requests
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            raise RuntimeError(f"下载视频失败: {str(e)}")

    def _generate_placeholder_video(
        self,
        output_dir: str,
        duration_sec: int,
        scene_index: int,
        message: str | None = None,
    ) -> str:
        """生成兜底占位视频，保证拼接时间线不断裂。"""
        output_path = os.path.join(output_dir, f"placeholder_{scene_index}_{uuid.uuid4().hex}.mp4")

        try:
            from moviepy import ColorClip
            # 创建一个黑色背景的占位视频
            clip = ColorClip(size=(1280, 720), color=(0, 0, 0), duration=duration_sec)
            clip.write_videofile(output_path, fps=24, logger=None)
            clip.close()
        except Exception:
            # 如果 moviepy 失败，创建一个空文件
            with open(output_path, "wb") as f:
                f.write(b"\x00\x00\x00\x00mock_video_placeholder")

        return output_path


video_composer = VideoComposer()
