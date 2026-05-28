"""视频生成服务（调用火山引擎视频生成模型）"""
import os
import uuid
import subprocess
import tempfile
import logging
import shutil
import math
from typing import Optional

# 查找 FFmpeg 路径
FFMPEG_PATH = shutil.which("ffmpeg") or r"C:\Users\练轩成\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"

from backend.providers import VolcanoLLM, VideoRequest
from backend.v1.app.models.frame import Frame
from backend.v1.app.video.service.ffmpeg_utils import ffmpeg_utils
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)


class VideoComposer:
    """视频生成服务（调用 Seedance 1.5）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.llm = VolcanoLLM(key=None, model_name=None)
        self.storage = get_storage_client()

    def compose(
        self,
        audio_path: str,
        scenes: list[dict],
        image_urls: list[str],
        output_dir: str,
    ) -> str:
        """
        生成最终视频。

        流程：
        1. 为每个场景调用视频生成模型
        2. 下载生成的视频到本地
        3. 拼接所有场景视频
        4. 返回本地视频路径（后续由调用方上传 TOS）

        :param audio_path: 配音音频路径（暂时未使用，视频生成模型自带音频）
        :param scenes: 场景列表（包含 text、duration、type 等）
        :param image_urls: 场景图片 HTTP URL 列表（作为首帧参考）
        :param output_dir: 输出目录
        :returns: 生成视频的本地路径
        """
        os.makedirs(output_dir, exist_ok=True)

        # 为每个场景生成视频
        video_paths = []
        for i, scene in enumerate(scenes):
            try:
                logger.info(f"[视频生成] 开始生成场景 {i + 1}/{len(scenes)}")
                image_url = image_urls[i] if i < len(image_urls) else None
                video_path = self._generate_scene_video(
                    scene=scene,
                    reference_image=image_url,
                    output_dir=output_dir,
                    scene_index=i,
                )
                video_paths.append(video_path)
                logger.info(f"[视频生成] 场景 {i + 1} 生成成功: {video_path}")
            except Exception as e:
                logger.error(f"[视频生成] 场景 {i + 1} 生成失败: {str(e)}")
                # 失败时使用占位视频
                placeholder_path = self._generate_placeholder_video(
                    output_dir, scene.get("duration", 5), i
                )
                video_paths.append(placeholder_path)

        # 拼接所有场景视频
        if len(video_paths) > 1:
            concat_path = self._concat_videos(video_paths, output_dir)
            return concat_path
        elif video_paths:
            return video_paths[0]

        # 如果所有场景都失败，返回占位视频
        return self._generate_placeholder_video(output_dir, 30, 0)

    def compose_frames(
        self,
        frames: list[Frame],
        output_dir: str,
    ) -> str:
        """
        为每个 Frame 生成视频片段并拼接。

        :param frames: Frame 对象列表（需包含 image_url、prompt、duration 等）
        :param output_dir: 输出目录
        :returns: 拼接后视频的本地路径
        """
        os.makedirs(output_dir, exist_ok=True)

        video_paths = []
        for i, frame in enumerate(frames):
            try:
                logger.info(f"[视频生成] 开始生成帧 {frame.sequence}/{len(frames)}")

                # 构造视频 prompt
                prompt = frame.prompt or frame.description or ""
                ai_params = frame.ai_params or {}
                camera = ai_params.get("camera", "")
                mood = ai_params.get("mood", "")
                if camera:
                    prompt += f"\n镜头运动：{camera}"
                if mood:
                    prompt += f"\n氛围：{mood}"

                # 时长限制（Seedance 1.5 i2v 模式固定 5 秒）
                generation_duration = 5
                target_dur = max(1.0, float(frame.duration or generation_duration))

                video_request = VideoRequest(
                    duration=generation_duration,
                    ratio="9:16",
                    generate_audio=False,
                    draft=False,
                    watermark=False,
                )

                # 首帧图片
                image_url = None
                if frame.image_url and frame.image_url.startswith("http"):
                    image_url = frame.image_url

                response = self.llm.generate_video_sync(
                    request=video_request,
                    prompt=prompt,
                    image=image_url,
                )

                if not response or not response.video_url:
                    raise ValueError("视频生成失败，未获取到视频 URL")

                local_path = os.path.join(output_dir, f"frame_{frame.sequence}_{uuid.uuid4().hex}.mp4")
                self._download_video(response.video_url, local_path)

                # 按 LLM 规划时长裁剪（Seedance 固定生成 5 秒，需裁剪到目标时长）
                target_dur = float(frame.duration)
                if target_dur < 5:
                    trimmed_path = os.path.join(output_dir, f"frame_{frame.sequence}_{uuid.uuid4().hex}_trimmed.mp4")
                    try:
                        ffmpeg_utils.split_video(local_path, trimmed_path, start=0, end=target_dur)
                        local_path = trimmed_path
                        logger.info(f"[视频裁剪] 帧 {frame.sequence} 裁剪到 {target_dur} 秒")
                    except Exception as trim_err:
                        logger.warning(f"[视频裁剪] 裁剪失败，使用原始 5 秒: {trim_err}")

                if target_dur > 5:
                    extended_path = os.path.join(output_dir, f"frame_{frame.sequence}_{uuid.uuid4().hex}_extended.mp4")
                    try:
                        loops = max(1, math.ceil(target_dur / 5) - 1)
                        cmd = [
                            FFMPEG_PATH,
                            "-y",
                            "-stream_loop", str(loops),
                            "-i", local_path,
                            "-t", str(target_dur),
                            "-c", "copy",
                            extended_path,
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                        if result.returncode != 0:
                            raise RuntimeError(result.stderr)
                        local_path = extended_path
                        logger.info(f"[视频补时] 帧 {frame.sequence} 补足到 {target_dur} 秒")
                    except Exception as extend_err:
                        logger.warning(f"[视频补时] 补时失败，使用原始 5 秒: {extend_err}")

                video_paths.append(local_path)

                frame.status = 2  # 已完成
                logger.info(f"[视频生成] 帧 {frame.sequence} 生成成功: {local_path}")
            except Exception as e:
                logger.error(f"[视频生成] 帧 {frame.sequence} 生成失败: {str(e)}")
                frame.status = 3  # 失败
                placeholder = self._generate_placeholder_video(
                    output_dir, int(float(frame.duration)), frame.sequence
                )
                video_paths.append(placeholder)

        # 拼接
        if len(video_paths) > 1:
            return self._concat_videos(video_paths, output_dir)
        elif video_paths:
            return video_paths[0]

        return self._generate_placeholder_video(output_dir, 30, 0)

    def _generate_scene_video(
        self,
        scene: dict,
        reference_image: Optional[str],
        output_dir: str,
        scene_index: int,
    ) -> str:
        """
        为单个场景生成视频。

        :param scene: 场景数据（包含 text、duration、type、visual）
        :param reference_image: 参考图片 HTTP URL（可选，作为首帧）
        :param output_dir: 输出目录
        :param scene_index: 场景索引
        :returns: 生成视频的本地路径
        """
        # 构造视频生成 prompt
        prompt = self._build_video_prompt(scene)

        # 获取时长
        duration = scene.get("duration", 5)
        # Seedance 1.5 i2v 模式固定 5 秒
        duration = 5

        # 构造视频生成请求
        video_request = VideoRequest(
            duration=duration,
            ratio="9:16",  # 竖屏视频
            generate_audio=False,  # 不生成音频，后续添加 TTS
            draft=False,
            watermark=False,
        )

        # 首帧图片：仅传有效 URL
        image_url = None
        if reference_image and reference_image.startswith("http"):
            image_url = reference_image

        # 调用视频生成模型（同步）
        response = self.llm.generate_video_sync(
            request=video_request,
            prompt=prompt,
            image=image_url,
        )

        if not response or not response.video_url:
            raise ValueError("视频生成失败，未获取到视频 URL")

        # 下载视频到本地
        local_path = os.path.join(output_dir, f"scene_{scene_index}_{uuid.uuid4().hex}.mp4")
        self._download_video(response.video_url, local_path)

        return local_path

    def _build_video_prompt(self, scene: dict) -> str:
        """
        构造视频生成的 prompt。

        :param scene: 场景数据（包含 text、type、visual）
        :returns: 视频生成 prompt
        """
        text = scene.get("text", "")
        scene_type = scene.get("type", "")
        visual = scene.get("visual", {})
        video_prompt = visual.get("video_prompt", "")
        camera = visual.get("camera", "")
        mood = visual.get("mood", "")

        # 优先使用 LLM 生成的 video_prompt
        if video_prompt:
            prompt = video_prompt
            if camera:
                prompt += f"\n镜头运动：{camera}"
            if mood:
                prompt += f"\n氛围：{mood}"
            return prompt

        # fallback: 旧格式构造
        source = visual.get("source", "")
        prompt = f"生成一个带货视频片段：{text}"
        if scene_type:
            prompt += f"\n场景类型：{scene_type}"
        if source:
            prompt += f"\n画面内容：{source}"
        prompt += "\n要求：画面清晰、流畅，适合竖屏带货视频风格。"

        return prompt

    def _concat_videos(self, video_paths: list[str], output_dir: str) -> str:
        """
        使用 FFmpeg 拼接多个视频片段。

        :param video_paths: 视频片段路径列表
        :param output_dir: 输出目录
        :returns: 拼接后的视频路径
        """
        output_path = os.path.join(output_dir, f"concat_{uuid.uuid4().hex}.mp4")

        # 创建 concat 文件列表
        concat_file = os.path.join(output_dir, f"concat_{uuid.uuid4().hex}.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for video_path in video_paths:
                # FFmpeg concat 需要转义路径中的特殊字符
                escaped_path = video_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        try:
            # 使用 FFmpeg concat 协议拼接视频
            cmd = [
                FFMPEG_PATH,
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-y",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.warning(f"[视频拼接] FFmpeg concat 失败: {result.stderr}")
                # 尝试使用 moviepy 作为 fallback
                return self._concat_videos_moviepy(video_paths, output_dir)

            logger.info(f"[视频拼接] FFmpeg concat 成功: {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"[视频拼接] FFmpeg concat 异常: {str(e)}")
            # 尝试使用 moviepy 作为 fallback
            return self._concat_videos_moviepy(video_paths, output_dir)
        finally:
            # 清理临时文件
            if os.path.exists(concat_file):
                os.remove(concat_file)

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

    def _generate_placeholder_video(self, output_dir: str, duration_sec: int, scene_index: int) -> str:
        """生成占位视频"""
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
