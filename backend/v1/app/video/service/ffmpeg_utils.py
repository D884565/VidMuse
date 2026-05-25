"""FFmpeg 工具类"""
import os
import subprocess
import json
from typing import Optional


class FFmpegUtils:
    """FFmpeg 工具类"""

    def get_video_info(self, video_path: str) -> dict:
        """
        获取视频元数据信息

        Args:
            video_path: 视频文件路径

        Returns:
            视频信息字典
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 使用 ffprobe 获取视频信息
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFprobe 执行失败: {e.stderr}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"解析 FFprobe 输出失败: {e}")

        # 提取视频流信息
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            raise RuntimeError("未找到视频流")

        # 提取格式信息
        format_info = data.get("format", {})

        # 计算帧率
        fps = 0.0
        if "r_frame_rate" in video_stream:
            try:
                num, den = map(int, video_stream["r_frame_rate"].split("/"))
                fps = num / den if den != 0 else 0.0
            except (ValueError, ZeroDivisionError):
                fps = 0.0

        return {
            "duration": float(format_info.get("duration", 0)),
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "format": format_info.get("format_name", ""),
            "file_size": int(format_info.get("size", 0)),
            "fps": fps,
        }

    def split_video(
        self,
        input_path: str,
        output_path: str,
        start: float,
        end: Optional[float] = None,
    ) -> str:
        """
        分割视频

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            start: 开始时间（秒）
            end: 结束时间（秒），None 表示到视频末尾

        Returns:
            输出文件路径
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"视频文件不存在: {input_path}")

        # 构建 FFmpeg 命令
        cmd = ["ffmpeg", "-y", "-i", input_path]

        # 设置开始时间
        if start > 0:
            cmd.extend(["-ss", str(start)])

        # 设置结束时间
        if end is not None:
            cmd.extend(["-to", str(end)])

        # 使用 copy 编码以保持原始质量
        cmd.extend(["-c", "copy", output_path])

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"视频分割失败: {e.stderr}")

        return output_path

    def replace_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        """
        替换视频音频

        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        # 构建 FFmpeg 命令
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path,
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频替换失败: {e.stderr}")

        return output_path

    def add_bgm(
        self,
        video_path: str,
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.3,
        original_volume: float = 1.0,
    ) -> str:
        """
        添加背景音乐

        Args:
            video_path: 视频文件路径
            bgm_path: 背景音乐文件路径
            output_path: 输出文件路径
            bgm_volume: BGM 音量（0-1）
            original_volume: 原音频音量（0-1）

        Returns:
            输出文件路径
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        if not os.path.exists(bgm_path):
            raise FileNotFoundError(f"BGM 文件不存在: {bgm_path}")

        # 构建 FFmpeg 命令
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", bgm_path,
            "-filter_complex",
            f"[0:a]volume={original_volume}[a0];[1:a]volume={bgm_volume}[a1];[a0][a1]amix=inputs=2:duration=first[out]",
            "-map", "0:v:0",
            "-map", "[out]",
            "-c:v", "copy",
            output_path,
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"添加 BGM 失败: {e.stderr}")

        return output_path

    def mix_audio_tracks(
        self,
        video_path: str,
        audio_paths: list[str],
        output_path: str,
        volumes: Optional[list[float]] = None,
    ) -> str:
        """
        混合多个音频轨道

        Args:
            video_path: 视频文件路径
            audio_paths: 音频文件路径列表
            output_path: 输出文件路径
            volumes: 各音频音量列表（0-1）

        Returns:
            输出文件路径
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        for audio_path in audio_paths:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        # 如果没有指定音量，默认都是 1.0
        if volumes is None:
            volumes = [1.0] * len(audio_paths)

        # 构建输入和滤镜
        inputs = ["-i", video_path]
        for audio_path in audio_paths:
            inputs.extend(["-i", audio_path])

        # 构建滤镜图
        filter_parts = []
        for i, (audio_path, volume) in enumerate(zip(audio_paths, volumes)):
            filter_parts.append(f"[{i + 1}:a]volume={volume}[a{i}]")

        # 混合所有音频
        mix_inputs = "".join(f"[a{i}]" for i in range(len(audio_paths)))
        filter_parts.append(f"{mix_inputs}amix=inputs={len(audio_paths)}:duration=first[out]")
        filter_complex = ";".join(filter_parts)

        # 构建完整命令
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[out]",
            "-c:v", "copy",
            output_path,
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频混合失败: {e.stderr}")

        return output_path


ffmpeg_utils = FFmpegUtils()
