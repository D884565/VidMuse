"""FFmpeg 工具类"""
import os
import uuid
import shutil
import subprocess
import json
import logging
from typing import Optional

from backend.v1.app.config.config import settings

logger = logging.getLogger(__name__)

FFMPEG_PATH = settings.FFMPEG_PATH or os.environ.get("FFMPEG_PATH") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH = settings.FFPROBE_PATH or os.environ.get("FFPROBE_PATH") or shutil.which("ffprobe") or "ffprobe"

# 各操作的超时秒数
_TIMEOUT_PROBE = 30
_TIMEOUT_SPLIT = 120
_TIMEOUT_AUDIO = 180


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
            FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_entries",
            "format=duration,size,format_name:stream=codec_type,width,height,r_frame_rate",
            video_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=False,
                check=True,
                timeout=_TIMEOUT_PROBE,
            )
            data = json.loads(result.stdout.decode("utf-8", errors="replace"))
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"FFprobe 执行超时 ({_TIMEOUT_PROBE}s): {video_path}")
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
        cmd = [FFMPEG_PATH, "-y", "-i", input_path]

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
                timeout=_TIMEOUT_SPLIT,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"视频分割超时 ({_TIMEOUT_SPLIT}s): {input_path}")
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
        替换视频音频，自动处理音视频时长不一致的情况。

        - 音频 > 视频：冻结最后一帧延长视频（避免截断配音/CTA）
        - 音频 <= 视频：音频末尾填充静音对齐视频时长

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

        video_duration = self.get_video_info(video_path)["duration"]
        audio_duration = self.get_audio_duration(audio_path)

        # 音频比视频长：需要延长视频来匹配音频，避免截断配音
        if audio_duration > video_duration:
            return self._replace_audio_extend_video(
                video_path, audio_path, output_path, video_duration, audio_duration
            )

        # 音频 <= 视频：用 apad 在音频末尾填充静音，对齐到视频时长
        # -t 截断输出到视频时长，确保音视频等长
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", f"[1:a]apad=whole_dur={video_duration}[a]",
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "[a]",
            "-t", str(video_duration),
            output_path,
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=_TIMEOUT_AUDIO,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"音频替换超时 ({_TIMEOUT_AUDIO}s): {video_path}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频替换失败: {e.stderr}")

        return output_path

    def get_audio_duration(self, audio_path: str) -> float:
        """用 ffprobe 获取音频文件时长（秒），失败时返回 0.0"""
        cmd = [
            FFPROBE_PATH,
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=_TIMEOUT_PROBE,
            )
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            # ffprobe 失败时返回 0，调用方会走音频<=视频的分支（即老逻辑）
            return 0.0

    def _replace_audio_extend_video(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        video_duration: float,
        audio_duration: float,
    ) -> str:
        """
        音频比视频长时，通过冻结最后一帧来延长视频，再合并音频。

        步骤：
        1. 从原视频提取最后一帧图片
        2. 用最后一帧生成一段静默视频（画面冻结，无声音）
        3. 把原视频和冻结视频拼接成一个完整视频
        4. 将 TTS 音频替换进拼接后的视频

        Args:
            video_path: 原视频路径
            audio_path: TTS 音频路径
            output_path: 输出路径
            video_duration: 原视频时长（秒）
            audio_duration: TTS 音频时长（秒）

        Returns:
            输出文件路径
        """
        output_dir = os.path.dirname(output_path)
        # 需要延长的时长 = 音频时长 - 视频时长，多留 0.5s 余量防止边界截断
        extend_duration = audio_duration - video_duration + 0.5

        # 所有临时文件共用一个 uid，方便 finally 清理
        uid = uuid.uuid4().hex
        last_frame_path = os.path.join(output_dir, f"_last_frame_{uid}.png")
        extend_video_path = os.path.join(output_dir, f"_extend_{uid}.mp4")
        concat_video_path = os.path.join(output_dir, f"_concat_{uid}.mp4")
        concat_list_path = os.path.join(output_dir, f"_concat_{uid}.txt")

        try:
            # 步骤 1：提取原视频最后一帧（-sseof -0.1 从末尾前 0.1 秒处取帧）
            subprocess.run(
                [FFMPEG_PATH, "-y", "-sseof", "-0.1", "-i", video_path,
                 "-frames:v", "1", "-q:v", "2", last_frame_path],
                capture_output=True, text=True, check=True, timeout=_TIMEOUT_SPLIT,
            )

            # 步骤 2：用最后一帧循环播放 + 静音音轨，生成延长片段
            # -loop 1 循环图片，anullsrc 生成静音，-t 控制时长
            subprocess.run(
                [FFMPEG_PATH, "-y",
                 "-loop", "1", "-i", last_frame_path,
                 "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                 "-t", str(extend_duration),
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest",
                 extend_video_path],
                capture_output=True, text=True, check=True, timeout=_TIMEOUT_SPLIT,
            )

            # 步骤 3：用 FFmpeg concat 协议把原视频和延长片段拼接
            with open(concat_list_path, "w", encoding="utf-8") as f:
                v1 = video_path.replace("\\", "/").replace("'", "'\\''")
                v2 = extend_video_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{v1}'\nfile '{v2}'\n")
            subprocess.run(
                [FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
                 "-i", concat_list_path, "-c", "copy", concat_video_path],
                capture_output=True, text=True, check=True, timeout=_TIMEOUT_SPLIT,
            )

            # 步骤 4：将 TTS 音频替换进拼接后的视频
            # 此时视频时长 >= 音频时长，apad 处理边界对齐，-t 截断到音频时长
            video_duration_new = self.get_video_info(concat_video_path)["duration"]
            cmd = [
                FFMPEG_PATH, "-y",
                "-i", concat_video_path,
                "-i", audio_path,
                "-filter_complex", f"[1:a]apad=whole_dur={video_duration_new}[a]",
                "-c:v", "copy",
                "-map", "0:v:0",
                "-map", "[a]",
                "-t", str(audio_duration),
                output_path,
            ]
            subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=_TIMEOUT_AUDIO,
            )

            return output_path

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"音频替换（视频延长）超时: {video_path}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频替换（视频延长）失败: {e.stderr}")
        finally:
            # 清理所有中间临时文件
            for p in [last_frame_path, extend_video_path, concat_video_path, concat_list_path]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass

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
            FFMPEG_PATH, "-y",
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
                timeout=_TIMEOUT_AUDIO,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"添加 BGM 超时 ({_TIMEOUT_AUDIO}s): {video_path}")
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
        cmd = [FFMPEG_PATH, "-y"] + inputs + [
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
                timeout=_TIMEOUT_AUDIO,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"音频混合超时 ({_TIMEOUT_AUDIO}s): {video_path}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频混合失败: {e.stderr}")

        return output_path


ffmpeg_utils = FFmpegUtils()
