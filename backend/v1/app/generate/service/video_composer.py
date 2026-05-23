"""视频合成服务"""
import os
import uuid
import json
import tempfile


class VideoComposer:
    """视频合成服务（当前返回 Mock 视频）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()

    def compose(
        self,
        audio_path: str,
        images: list[str],
        subtitles: list[dict],
        output_dir: str,
    ) -> str:
        """
        合成最终视频。

        :param audio_path: 配音音频路径
        :param images: 场景图片路径列表
        :param subtitles: 字幕数据（剧本 body）
        :param output_dir: 输出目录
        :returns: 合成视频的本地路径（后续由调用方上传 MinIO）
        """
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.mp4")
        self._generate_placeholder_video(output_path, duration_sec=sum(
            s.get("duration_sec", 5) for s in subtitles
        ))
        return output_path

    def _generate_placeholder_video(self, path: str, duration_sec: int):
        """生成占位 MP4（后续替换为 ffmpeg 或 moviepy 渲染）"""
        # Mock：创建一个文本文件作为占位（后续接入真实渲染引擎）
        with open(path + ".txt", "w") as f:
            json.dump({
                "mock_video": True,
                "duration_sec": duration_sec,
                "output_path": path,
            }, f)
        # 创建一个空 mp4 占位
        with open(path, "wb") as f:
            f.write(b"\x00\x00\x00\x00mock_video_placeholder")


video_composer = VideoComposer()
