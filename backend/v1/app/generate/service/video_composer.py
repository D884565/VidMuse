"""视频生成服务（调用火山引擎视频生成模型）"""
import os
import uuid
import tempfile
import logging
import asyncio
from typing import Optional

from backend.providers import VolcanoLLM, VideoRequest
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
        images: list[str],
        subtitles: list[dict],
        output_dir: str,
    ) -> str:
        """
        生成最终视频。

        流程：
        1. 为每个场景调用视频生成模型
        2. 下载生成的视频到本地
        3. 返回本地视频路径（后续由调用方上传 TOS）

        :param audio_path: 配音音频路径（暂时未使用，视频生成模型自带音频）
        :param images: 场景图片路径列表（可作为首帧参考）
        :param subtitles: 字幕数据（剧本 body）
        :param output_dir: 输出目录
        :returns: 生成视频的本地路径
        """
        os.makedirs(output_dir, exist_ok=True)

        # 为每个场景生成视频
        video_paths = []
        for i, scene in enumerate(subtitles):
            try:
                logger.info(f"[视频生成] 开始生成场景 {i + 1}/{len(subtitles)}")
                video_path = self._generate_scene_video(
                    scene=scene,
                    reference_image=images[i] if i < len(images) else None,
                    output_dir=output_dir,
                    scene_index=i,
                )
                video_paths.append(video_path)
                logger.info(f"[视频生成] 场景 {i + 1} 生成成功: {video_path}")
            except Exception as e:
                logger.error(f"[视频生成] 场景 {i + 1} 生成失败: {str(e)}")
                # 失败时使用占位视频
                placeholder_path = self._generate_placeholder_video(
                    output_dir, scene.get("duration_sec", 5), i
                )
                video_paths.append(placeholder_path)

        # 返回第一个视频路径（暂时不做拼接，后续可以扩展）
        # TODO: 后续可以使用 ffmpeg/moviepy 拼接多个视频片段
        if video_paths:
            return video_paths[0]

        # 如果所有场景都失败，返回占位视频
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

        :param scene: 场景数据（包含 text、duration_sec、image_keyword）
        :param reference_image: 参考图片路径（可选，作为首帧）
        :param output_dir: 输出目录
        :param scene_index: 场景索引
        :returns: 生成视频的本地路径
        """
        # 构造视频生成 prompt
        prompt = self._build_video_prompt(scene)

        # 获取时长（秒转为模型要求的格式）
        duration = scene.get("duration_sec", 5)
        # 限制时长在模型支持的范围内（通常 2-10 秒）
        duration = max(2, min(10, duration))

        # 构造视频生成请求
        video_request = VideoRequest(
            duration=duration,
            ratio="16:9",
            generate_audio=False,  # 不生成音频，后续添加 TTS
            draft=False,
            watermark=False,
        )

        # 首帧图片：仅传有效 URL，本地占位文件不传
        image_url = None
        if reference_image and reference_image.startswith("http"):
            image_url = reference_image

        # 调用视频生成模型（异步）
        response = asyncio.run(self.llm.generate_video(
            request=video_request,
            prompt=prompt,
            image=image_url,
        ))

        if not response or not response.video_url:
            raise ValueError("视频生成失败，未获取到视频 URL")

        # 下载视频到本地
        local_path = os.path.join(output_dir, f"scene_{scene_index}_{uuid.uuid4().hex}.mp4")
        self._download_video(response.video_url, local_path)

        return local_path

    def _build_video_prompt(self, scene: dict) -> str:
        """
        构造视频生成的 prompt。

        :param scene: 场景数据
        :returns: 视频生成 prompt
        """
        text = scene.get("text", "")
        image_keyword = scene.get("image_keyword", "")

        # 构造详细的视频描述 prompt
        prompt = f"生成一个带货视频片段：{text}"
        if image_keyword:
            prompt += f"\n场景关键词：{image_keyword}"
        prompt += "\n要求：画面清晰、流畅，适合带货视频风格。"

        return prompt

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
