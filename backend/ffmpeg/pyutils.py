"""FFmpeg 统一视频/音频处理工具。

所有 FFmpeg 相关功能集中在本模块：
- 视频元数据获取、分割、拼接
- 音频替换、BGM 混入、多轨混合
- 静音生成、音频时长适配、音频拼接
- 视频下载（HTTP/本地）
- 首帧提取

外部统一入口: ffmpeg_tool (FFmpegVideoTool 单例)
"""
import subprocess
import json
import os
import shutil
import tempfile
import threading
import uuid
from fractions import Fraction
from typing import List, Dict, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

from backend.v1.app.config.config import settings

# ---------------------------------------------------------------------------
# 模块级路径常量（供外部 from backend.ffmpeg import FFMPEG_PATH 使用）
# ---------------------------------------------------------------------------
FFMPEG_PATH: str = settings.FFMPEG_PATH or os.environ.get("FFMPEG_PATH") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH: str = settings.FFPROBE_PATH or os.environ.get("FFPROBE_PATH") or shutil.which("ffprobe") or "ffprobe"

# ---------------------------------------------------------------------------
# 各操作超时（秒）
# ---------------------------------------------------------------------------
_TIMEOUT_PROBE = 30
_TIMEOUT_SPLIT = 120
_TIMEOUT_AUDIO = 180


# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass
class VideoMetadata:
    """视频元数据结构"""
    duration: float
    width: int
    height: int
    fps: float
    bitrate: int
    codec: str
    pixel_format: str
    total_frames: Optional[int] = None
    audio_codec: Optional[str] = None
    sample_rate: Optional[int] = None

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


@dataclass
class SegmentResult:
    """分割结果结构"""
    segment_path: str
    first_frame_path: str
    start_time: float
    end_time: float
    duration: float
    segment_bytes: Optional[bytes] = field(default=None, repr=False)
    frame_bytes: Optional[bytes] = field(default=None, repr=False)


# ===========================================================================
# FFmpegVideoTool
# ===========================================================================

class FFmpegVideoTool:
    """
    FFmpeg 统一视频/音频处理工具类。

    功能：
    - 视频元数据获取（get_video_info / get_metadata）
    - 视频分割（split_video）与首帧提取（extract_first_frame）
    - 视频下载（download_video）与一站式处理（process_url）
    - 音频替换（replace_audio），自动处理音视频时长不一致
    - 背景音乐添加（add_bgm）与多轨混合（mix_audio_tracks）
    - 静音音频生成（create_silent_audio_for_duration）
    - 音频时长适配（fit_audio_to_duration）与拼接（concat_audio_clips）
    - 自动清理临时文件
    """

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
        temp_dir: Optional[str] = None,
        auto_cleanup: bool = True,
        chunk_size: int = 8192,
    ):
        self.ffmpeg = ffmpeg_path or FFMPEG_PATH
        self.ffprobe = ffprobe_path or FFPROBE_PATH
        self.chunk_size = chunk_size
        self.auto_cleanup = auto_cleanup

        # 创建临时目录
        self.temp_dir = temp_dir or tempfile.gettempdir()
        os.makedirs(self.temp_dir, exist_ok=True)

        # 跟踪所有创建的文件用于清理
        self._managed_files: set = set()
        self._lock = threading.Lock()

        self._validate_tools()

    def __del__(self):
        """析构时自动清理"""
        if self.auto_cleanup:
            self.cleanup()

    # -----------------------------------------------------------------------
    # 内部工具
    # -----------------------------------------------------------------------

    def _validate_tools(self):
        """验证 FFmpeg / FFprobe 可用"""
        for tool in [self.ffmpeg, self.ffprobe]:
            try:
                result = subprocess.run(
                    [tool, "-version"], capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"{tool} 返回错误")
            except FileNotFoundError:
                raise RuntimeError(f"未找到 {tool}，请确保 FFmpeg 已安装")

    def _run_command(
        self,
        cmd: List[str],
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        """执行命令，返回 (returncode, stdout, stderr)。"""
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
        )
        return result.returncode, result.stdout, result.stderr

    def _run_checked(self, cmd: List[str], timeout: Optional[int] = None) -> None:
        """执行命令，失败或超时直接抛异常。"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"FFmpeg 命令超时 ({timeout}s): {' '.join(cmd[:4])}...")
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 命令失败: {result.stderr}")

    def _track_file(self, path: str):
        """跟踪文件以便清理"""
        with self._lock:
            self._managed_files.add(os.path.abspath(path))

    def _generate_temp_path(self, suffix: str = "", prefix: str = "tmp") -> str:
        """生成临时文件路径"""
        name = f"{prefix}_{uuid.uuid4().hex[:8]}{suffix}"
        path = os.path.join(self.temp_dir, name)
        self._track_file(path)
        return path

    def cleanup(self):
        """清理所有临时文件"""
        with self._lock:
            for path in list(self._managed_files):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                except OSError:
                    pass
            self._managed_files.clear()

            # 清理临时目录（如果是内部创建的）
            try:
                if os.path.exists(self.temp_dir) and not os.listdir(self.temp_dir):
                    os.rmdir(self.temp_dir)
            except OSError:
                pass

    # -----------------------------------------------------------------------
    # 视频元数据
    # -----------------------------------------------------------------------

    def get_video_info(self, video_path: str) -> dict:
        """获取视频元数据，返回 dict（兼容 ffmpeg_utils 接口）。

        Returns:
            {"duration", "width", "height", "format", "file_size", "fps"}
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        cmd = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_entries",
            "format=duration,size,format_name:stream=codec_type,width,height,r_frame_rate",
            video_path,
        ]

        returncode, stdout, stderr = self._run_command(cmd, timeout=_TIMEOUT_PROBE)
        if returncode != 0:
            raise RuntimeError(f"FFprobe 执行失败: {stderr}")

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"解析 FFprobe 输出失败: {e}")

        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            raise RuntimeError("未找到视频流")

        format_info = data.get("format", {})

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

    def get_metadata(self, video_path: str) -> VideoMetadata:
        """获取视频元数据，返回 VideoMetadata 结构体。"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        cmd = [
            self.ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path,
        ]
        returncode, stdout, stderr = self._run_command(cmd, timeout=_TIMEOUT_PROBE)

        if returncode != 0:
            raise RuntimeError(f"ffprobe 失败: {stderr}")

        data = json.loads(stdout)

        video_stream = None
        audio_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream

        if video_stream is None:
            raise RuntimeError("未找到视频流")

        duration = float(video_stream.get("duration", 0))
        if duration == 0:
            duration = float(data.get("format", {}).get("duration", 0))

        fps_str = video_stream.get("r_frame_rate", "0/1")
        try:
            fps = float(Fraction(fps_str))
        except (ValueError, ZeroDivisionError):
            fps = 0.0

        bitrate_str = video_stream.get("bit_rate") or data.get("format", {}).get("bit_rate", "0")
        bitrate = int(bitrate_str) if bitrate_str else 0

        total_frames = None
        if video_stream.get("nb_frames"):
            total_frames = int(video_stream["nb_frames"])
        elif duration > 0 and fps > 0:
            total_frames = int(duration * fps)

        return VideoMetadata(
            duration=duration,
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=fps,
            bitrate=bitrate,
            codec=video_stream.get("codec_name", "unknown"),
            pixel_format=video_stream.get("pix_fmt", "unknown"),
            total_frames=total_frames,
            audio_codec=audio_stream.get("codec_name") if audio_stream else None,
            sample_rate=int(audio_stream["sample_rate"]) if audio_stream and audio_stream.get("sample_rate") else None,
        )

    # -----------------------------------------------------------------------
    # 音频元数据
    # -----------------------------------------------------------------------

    def get_audio_duration(self, audio_path: str) -> float:
        """用 ffprobe 获取音频文件时长（秒），失败时返回 0.0"""
        cmd = [
            self.ffprobe,
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
        except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
            return 0.0

    # -----------------------------------------------------------------------
    # 视频分割
    # -----------------------------------------------------------------------

    def split_video(
        self,
        input_path: Optional[str] = None,
        output_path: Optional[str] = None,
        start: float = 0,
        end: Optional[float] = None,
        *,
        # 以下参数用于列表分割模式（split_video_segments）
        output_dir: Optional[str] = None,
        video_path: Optional[str] = None,
        segment_duration: Optional[float] = None,
        segment_times: Optional[List[float]] = None,
        segment_count: Optional[int] = None,
        extract_first_frame: bool = False,
        frame_format: str = "jpg",
        frame_size: Optional[Tuple[int, int]] = None,
        copy_codecs: bool = False,
        segment_prefix: str = "segment",
        load_as_bytes: bool = False,
        keep_files: bool = False,
    ) -> Union[str, List[SegmentResult]]:
        """
        分割视频。

        两种调用模式：
        1. 简单模式：split_video(input, output, start, end) -> str
           按 start/end 截取一段，返回输出路径。

        2. 列表模式：split_video(video_path=..., segment_duration=...) -> List[SegmentResult]
           按时间段/数量分割成多段，返回结果列表。

        Args:
            input_path: 输入视频路径（简单模式必填；列表模式可选，作为 video_path 备选）
            output_path: 输出视频路径（简单模式必填）
            start: 开始时间-秒（简单模式）
            end: 结束时间-秒，None 表示到视频末尾（简单模式）
            video_path: 输入视频路径（列表模式，优先级高于 input_path）
            output_dir: 输出目录（列表模式）
            segment_duration: 每段时长（列表模式）
            segment_times: 自定义分割时间点（列表模式）
            segment_count: 按数量分割（列表模式）
            extract_first_frame: 是否提取首帧（列表模式）
            frame_format: 首帧格式（列表模式）
            frame_size: 首帧尺寸（列表模式）
            copy_codecs: 是否 copy 编码（列表模式）
            segment_prefix: 段文件名前缀（列表模式）
            load_as_bytes: 是否加载为字节流（列表模式）
            keep_files: 是否保留磁盘文件（列表模式）

        Returns:
            str（简单模式）或 List[SegmentResult]（列表模式）
        """
        # 列表模式
        if (
            video_path is not None
            or segment_duration is not None
            or segment_times is not None
            or segment_count is not None
        ):
            src = video_path or input_path
            if not src:
                raise ValueError("列表模式下 video_path 或 input_path 至少需要一个")
            return self._split_video_segments(
                video_path=src,
                output_dir=output_dir,
                segment_duration=segment_duration,
                segment_times=segment_times,
                segment_count=segment_count,
                extract_first_frame=extract_first_frame,
                frame_format=frame_format,
                frame_size=frame_size,
                copy_codecs=copy_codecs,
                segment_prefix=segment_prefix,
                load_as_bytes=load_as_bytes,
                keep_files=keep_files,
            )

        # 简单模式
        if not input_path:
            raise ValueError("简单模式下 input_path 为必填参数")
        if not output_path:
            raise ValueError("简单模式下 output_path 为必填参数")
        return self._split_video_simple(input_path, output_path, start, end)

    def _split_video_simple(
        self,
        input_path: str,
        output_path: str,
        start: float,
        end: Optional[float],
    ) -> str:
        """简单分割：截取 [start, end) 片段。"""
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"视频文件不存在: {input_path}")

        cmd = [self.ffmpeg, "-y", "-i", input_path]
        if start > 0:
            cmd.extend(["-ss", str(start)])
        if end is not None:
            cmd.extend(["-to", str(end)])
        cmd.extend(["-c", "copy", output_path])

        try:
            self._run_checked(cmd, timeout=_TIMEOUT_SPLIT)
        except RuntimeError as e:
            raise RuntimeError(f"视频分割失败: {e}")
        return output_path

    def _split_video_segments(
        self,
        video_path: str,
        output_dir: Optional[str] = None,
        segment_duration: Optional[float] = None,
        segment_times: Optional[List[float]] = None,
        segment_count: Optional[int] = None,
        extract_first_frame: bool = True,
        frame_format: str = "jpg",
        frame_size: Optional[Tuple[int, int]] = None,
        copy_codecs: bool = False,
        segment_prefix: str = "segment",
        load_as_bytes: bool = False,
        keep_files: bool = False,
    ) -> List[SegmentResult]:
        """列表分割：将视频分成多段。"""
        actual_path = video_path
        downloaded = False
        if video_path.startswith(("http://", "https://", "ftp://")):
            actual_path = self.download_video(video_path)
            downloaded = True

        if not os.path.exists(actual_path):
            raise FileNotFoundError(f"视频文件不存在: {actual_path}")

        if output_dir is None:
            output_dir = self._generate_temp_path(prefix="segments")
            os.makedirs(output_dir, exist_ok=True)
        else:
            os.makedirs(output_dir, exist_ok=True)
            self._track_file(output_dir)

        metadata = self.get_metadata(actual_path)
        duration = metadata.duration

        # 计算分割时间点
        if segment_duration:
            times = [i * segment_duration for i in range(int(duration / segment_duration) + 1)]
            times.append(duration)
        elif segment_times:
            times = sorted([0.0] + [t for t in segment_times if 0 < t < duration] + [duration])
        elif segment_count:
            step = duration / segment_count
            times = [i * step for i in range(segment_count + 1)]
        else:
            raise ValueError("必须指定 segment_duration、segment_times 或 segment_count 之一")

        times = sorted(list(set([round(t, 3) for t in times])))
        if times[-1] < duration:
            times.append(duration)

        results = []

        for i in range(len(times) - 1):
            start_time = times[i]
            end_time = times[i + 1]
            seg_duration = round(end_time - start_time, 3)

            if seg_duration <= 0.001:
                continue

            seg_filename = f"{segment_prefix}_{i:04d}.mp4"
            seg_path = os.path.join(output_dir, seg_filename)

            cmd = [self.ffmpeg, "-y", "-ss", str(start_time), "-i", actual_path, "-t", str(seg_duration)]

            if copy_codecs:
                cmd.extend(["-c", "copy", "-avoid_negative_ts", "make_zero", "-fflags", "+genpts"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-b:a", "128k"])
                if metadata.fps > 0:
                    cmd.extend(["-r", str(metadata.fps)])

            cmd.append(seg_path)

            returncode, _, stderr = self._run_command(cmd, timeout=300)
            if returncode != 0:
                raise RuntimeError(f"分割第 {i} 段失败: {stderr}")

            self._track_file(seg_path)

            # 提取首帧
            frame_path = None
            if extract_first_frame:
                frame_filename = f"{segment_prefix}_{i:04d}_frame.{frame_format}"
                frame_path = os.path.join(output_dir, frame_filename)
                try:
                    self.extract_first_frame(
                        seg_path, frame_path, 0,
                        width=frame_size[0] if frame_size else None,
                        height=frame_size[1] if frame_size else None,
                    )
                except Exception:
                    frame_path = None

            # 加载字节流
            segment_bytes = None
            frame_bytes = None

            if load_as_bytes:
                if os.path.exists(seg_path):
                    with open(seg_path, "rb") as f:
                        segment_bytes = f.read()
                if frame_path and os.path.exists(frame_path):
                    with open(frame_path, "rb") as f:
                        frame_bytes = f.read()

                if not keep_files:
                    try:
                        os.remove(seg_path)
                        self._managed_files.discard(os.path.abspath(seg_path))
                    except OSError:
                        pass
                    if frame_path:
                        try:
                            os.remove(frame_path)
                            self._managed_files.discard(os.path.abspath(frame_path))
                        except OSError:
                            pass

            results.append(SegmentResult(
                segment_path=os.path.abspath(seg_path) if (not load_as_bytes or keep_files) else "",
                first_frame_path=os.path.abspath(frame_path) if (
                    frame_path and (not load_as_bytes or keep_files)) else "",
                start_time=start_time,
                end_time=end_time,
                duration=seg_duration,
                segment_bytes=segment_bytes,
                frame_bytes=frame_bytes,
            ))

        # 清理下载的原始文件
        if downloaded and not keep_files:
            try:
                os.remove(actual_path)
                self._managed_files.discard(os.path.abspath(actual_path))
            except OSError:
                pass

        return results

    # -----------------------------------------------------------------------
    # 首帧提取
    # -----------------------------------------------------------------------

    def extract_first_frame(
        self,
        video_path: str,
        output_path: str,
        timestamp: float = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> str:
        """提取指定时间点帧"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        filters = []
        if width and height:
            filters.append(
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
            )
        elif width:
            filters.append(f"scale={width}:-1")
        elif height:
            filters.append(f"scale=-1:{height}")

        vf = ",".join(filters) if filters else ""

        cmd = [self.ffmpeg, "-y", "-ss", str(timestamp), "-i", video_path, "-frames:v", "1", "-q:v", "2"]
        if vf:
            cmd.extend(["-vf", vf])

        ext = os.path.splitext(output_path)[1].lower()
        if ext == ".png":
            cmd.extend(["-c:v", "png"])
        elif ext == ".webp":
            cmd.extend(["-c:v", "libwebp"])

        cmd.append(output_path)

        returncode, _, stderr = self._run_command(cmd, timeout=60)
        if returncode != 0:
            raise RuntimeError(f"提取首帧失败: {stderr}")

        self._track_file(output_path)
        return os.path.abspath(output_path)

    # -----------------------------------------------------------------------
    # 音频替换
    # -----------------------------------------------------------------------

    def replace_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        """
        替换视频音频，自动处理音视频时长不一致。

        - 音频 > 视频：冻结最后一帧延长视频（避免截断配音/CTA）
        - 音频 <= 视频：音频末尾填充静音对齐视频时长
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        video_duration = self.get_video_info(video_path)["duration"]
        audio_duration = self.get_audio_duration(audio_path)

        if audio_duration > video_duration:
            return self._replace_audio_extend_video(
                video_path, audio_path, output_path, video_duration, audio_duration,
            )

        # 音频 <= 视频：apad 填充静音 + -t 截断
        cmd = [
            self.ffmpeg, "-y",
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
            self._run_checked(cmd, timeout=_TIMEOUT_AUDIO)
        except RuntimeError as e:
            raise RuntimeError(f"音频替换失败: {e}")

        return output_path

    def _replace_audio_extend_video(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        video_duration: float,
        audio_duration: float,
    ) -> str:
        """音频比视频长时，冻结最后一帧延长视频再合并音频。"""
        output_dir = os.path.dirname(output_path) or self.temp_dir
        extend_duration = audio_duration - video_duration + 0.5

        uid = uuid.uuid4().hex
        last_frame_path = os.path.join(output_dir, f"_last_frame_{uid}.png")
        extend_video_path = os.path.join(output_dir, f"_extend_{uid}.mp4")
        concat_video_path = os.path.join(output_dir, f"_concat_{uid}.mp4")
        concat_list_path = os.path.join(output_dir, f"_concat_{uid}.txt")

        try:
            # 步骤 1：提取最后一帧
            self._run_checked(
                [self.ffmpeg, "-y", "-sseof", "-0.1", "-i", video_path,
                 "-frames:v", "1", "-q:v", "2", last_frame_path],
                timeout=_TIMEOUT_SPLIT,
            )

            # 步骤 2：最后一帧生成延长片段（静音）
            self._run_checked(
                [self.ffmpeg, "-y",
                 "-loop", "1", "-i", last_frame_path,
                 "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                 "-t", str(extend_duration),
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest",
                 extend_video_path],
                timeout=_TIMEOUT_SPLIT,
            )

            # 步骤 3：concat 拼接原视频和延长片段
            with open(concat_list_path, "w", encoding="utf-8") as f:
                v1 = video_path.replace("\\", "/").replace("'", "'\\''")
                v2 = extend_video_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{v1}'\nfile '{v2}'\n")
            self._run_checked(
                [self.ffmpeg, "-y", "-f", "concat", "-safe", "0",
                 "-i", concat_list_path, "-c", "copy", concat_video_path],
                timeout=_TIMEOUT_SPLIT,
            )

            # 步骤 4：将 TTS 音频替换进拼接后的视频
            video_duration_new = self.get_video_info(concat_video_path)["duration"]
            self._run_checked(
                [self.ffmpeg, "-y",
                 "-i", concat_video_path,
                 "-i", audio_path,
                 "-filter_complex", f"[1:a]apad=whole_dur={video_duration_new}[a]",
                 "-c:v", "copy",
                 "-map", "0:v:0",
                 "-map", "[a]",
                 "-t", str(audio_duration),
                 output_path],
                timeout=_TIMEOUT_AUDIO,
            )

            return output_path

        finally:
            for p in [last_frame_path, extend_video_path, concat_video_path, concat_list_path]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass

    # -----------------------------------------------------------------------
    # BGM / 多轨混合
    # -----------------------------------------------------------------------

    def add_bgm(
        self,
        video_path: str,
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.3,
        original_volume: float = 1.0,
    ) -> str:
        """添加背景音乐"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        if not os.path.exists(bgm_path):
            raise FileNotFoundError(f"BGM 文件不存在: {bgm_path}")

        cmd = [
            self.ffmpeg, "-y",
            "-i", video_path,
            "-stream_loop", "-1", "-i", bgm_path,  # 循环 BGM 直到视频结束
            "-filter_complex",
            f"[0:a]volume={original_volume}[a0];[1:a]volume={bgm_volume}[a1];[a0][a1]amix=inputs=2:duration=first[out]",
            "-map", "0:v:0",
            "-map", "[out]",
            "-c:v", "copy",
            output_path,
        ]

        try:
            self._run_checked(cmd, timeout=_TIMEOUT_AUDIO)
        except RuntimeError as e:
            raise RuntimeError(f"添加 BGM 失败: {e}")

        return output_path

    def mix_audio_tracks(
        self,
        video_path: str,
        audio_paths: list[str],
        output_path: str,
        volumes: Optional[list[float]] = None,
    ) -> str:
        """混合多个音频轨道"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        for audio_path in audio_paths:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        if volumes is None:
            volumes = [1.0] * len(audio_paths)

        inputs = ["-i", video_path]
        for audio_path in audio_paths:
            inputs.extend(["-i", audio_path])

        filter_parts = []
        for i, volume in enumerate(volumes):
            filter_parts.append(f"[{i + 1}:a]volume={volume}[a{i}]")

        mix_inputs = "".join(f"[a{i}]" for i in range(len(audio_paths)))
        filter_parts.append(f"{mix_inputs}amix=inputs={len(audio_paths)}:duration=first[out]")
        filter_complex = ";".join(filter_parts)

        cmd = [self.ffmpeg, "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[out]",
            "-c:v", "copy",
            output_path,
        ]

        try:
            self._run_checked(cmd, timeout=_TIMEOUT_AUDIO)
        except RuntimeError as e:
            raise RuntimeError(f"音频混合失败: {e}")

        return output_path

    # -----------------------------------------------------------------------
    # 视频拼接 / 循环
    # -----------------------------------------------------------------------

    def concat_videos(
        self,
        video_paths: list[str],
        output_path: str,
    ) -> str:
        """使用 FFmpeg concat demuxer 拼接多个视频。"""
        if not video_paths:
            raise ValueError("video_paths 不能为空")
        output_dir = os.path.dirname(output_path) or self.temp_dir
        concat_file = os.path.join(output_dir, f"_concat_{uuid.uuid4().hex}.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for vp in video_paths:
                escaped = vp.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
        try:
            self._run_checked(
                [self.ffmpeg, "-y", "-f", "concat", "-safe", "0",
                 "-i", concat_file, "-c", "copy", output_path],
                timeout=300,
            )
        finally:
            try:
                os.remove(concat_file)
            except OSError:
                pass
        self._track_file(output_path)
        return output_path

    def loop_video(
        self,
        input_path: str,
        output_path: str,
        target_duration: float,
    ) -> str:
        """循环视频至目标时长（-stream_loop + -t）。"""
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"视频文件不存在: {input_path}")

        info = self.get_video_info(input_path)
        source_dur = info["duration"]
        if source_dur <= 0:
            raise RuntimeError("无法获取源视频时长")

        loops = max(1, int(target_duration / source_dur))
        cmd = [
            self.ffmpeg, "-y",
            "-stream_loop", str(loops),
            "-i", input_path,
            "-t", str(target_duration),
            "-c", "copy",
            output_path,
        ]
        try:
            self._run_checked(cmd, timeout=120)
        except RuntimeError as e:
            raise RuntimeError(f"视频循环失败: {e}")
        self._track_file(output_path)
        return output_path

    # -----------------------------------------------------------------------
    # 音频工具（原 tts.py 中的 FFmpeg 操作）
    # -----------------------------------------------------------------------

    def create_silent_audio_for_duration(
        self,
        duration_sec: float,
        output_path: Optional[str] = None,
        sample_rate: int = 44100,
        channels: str = "mono",
    ) -> str:
        """生成指定时长的静音 mp3 文件。"""
        output_path = output_path or self._generate_temp_path(suffix=".mp3", prefix="silent")
        safe_duration = max(1.0, float(duration_sec or 1.0))
        cmd = [
            self.ffmpeg, "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl={channels}",
            "-t", str(safe_duration),
            "-q:a", "9",
            "-acodec", "libmp3lame",
            output_path,
        ]
        try:
            self._run_checked(cmd, timeout=30)
        except RuntimeError as e:
            raise RuntimeError(f"创建静音音频失败: {e}")
        self._track_file(output_path)
        return output_path

    def fit_audio_to_duration(
        self,
        input_path: str,
        duration_sec: float,
        output_path: Optional[str] = None,
    ) -> str:
        """将音频适配到指定时长（短则填充静音，长则截断）。"""
        output_path = output_path or self._generate_temp_path(suffix=".mp3", prefix="fit")
        safe_duration = max(1.0, float(duration_sec or 1.0))
        cmd = [
            self.ffmpeg, "-y",
            "-i", input_path,
            "-af", f"apad=whole_dur={safe_duration}",
            "-t", str(safe_duration),
            "-q:a", "2",
            output_path,
        ]
        try:
            self._run_checked(cmd, timeout=60)
        except RuntimeError as e:
            raise RuntimeError(f"音频时长适配失败: {e}")
        self._track_file(output_path)
        return output_path

    def concat_audio_clips(
        self,
        audio_paths: list[str],
        output_path: Optional[str] = None,
    ) -> str:
        """拼接多个音频文件。"""
        if not audio_paths:
            raise ValueError("audio_paths 不能为空")
        output_path = output_path or self._generate_temp_path(suffix=".mp3", prefix="concat")
        concat_file = self._generate_temp_path(suffix=".txt", prefix="concat_list")
        with open(concat_file, "w", encoding="utf-8") as f:
            for audio_path in audio_paths:
                escaped = audio_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
        try:
             self._run_checked(
                 [self.ffmpeg, "-y",
                  "-f", "concat", "-safe", "0",
                  "-i", concat_file,
                  "-c:a", "libmp3lame",
                  "-q:a", "2",
                  output_path],
                 timeout=60,
             )
        finally:
            try:
                os.remove(concat_file)
            except OSError:
                pass
        self._track_file(output_path)
        return output_path

    def append_tail_silence(
        self,
        input_path: str,
        tail_seconds: float,
        output_path: Optional[str] = None,
    ) -> str:
        """在音频末尾追加一小段静音，避免句尾贴边。"""
        safe_tail_seconds = max(0.0, float(tail_seconds or 0.0))
        if safe_tail_seconds <= 0:
            return input_path

        output_path = output_path or self._generate_temp_path(suffix=".mp3", prefix="tailpad")
        cmd = [
            self.ffmpeg, "-y",
            "-i", input_path,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[aout]",
            "-map", "[aout]",
            "-t", str(self.get_audio_duration(input_path) + safe_tail_seconds),
            "-c:a", "mp3",
            "-q:a", "2",
            output_path,
        ]
        try:
            self._run_checked(cmd, timeout=60)
        except RuntimeError as e:
            raise RuntimeError(f"音频尾部补静音失败: {e}")
        self._track_file(output_path)
        return output_path

    # -----------------------------------------------------------------------
    # 下载
    # -----------------------------------------------------------------------

    def download_video(
        self,
        url: str,
        output_path: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 300,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """下载视频文件（HTTP/HTTPS URL 或本地路径直接返回）。"""
        if os.path.isfile(url):
            if output_path:
                shutil.copy2(url, output_path)
                self._track_file(output_path)
                return output_path
            return url

        if output_path is None:
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1] or ".mp4"
            output_path = self._generate_temp_path(suffix=ext, prefix="download")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        cmd = [self.ffmpeg, "-y"]
        if headers:
            for key, value in headers.items():
                cmd.extend(["-headers", f"{key}: {value}"])
        cmd.extend([
            "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
            "-i", url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            output_path,
        ])

        returncode, _, stderr = self._run_command(cmd, timeout=timeout)

        if returncode != 0:
            try:
                self._download_with_urllib(url, output_path, headers, timeout, progress_callback)
            except Exception as e:
                raise RuntimeError(f"下载失败 (ffmpeg: {stderr}, urllib: {e})")

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("下载完成但文件为空")

        self._track_file(output_path)
        return os.path.abspath(output_path)

    def _download_with_urllib(
        self,
        url: str,
        output_path: str,
        headers: Optional[Dict[str, str]],
        timeout: int,
        progress_callback: Optional[Callable[[int, int], None]],
    ):
        """使用 urllib 下载（备用方案）"""
        import urllib.request

        req = urllib.request.Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=timeout) as response:
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                while True:
                    chunk = response.read(self.chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

    # -----------------------------------------------------------------------
    # 一站式处理
    # -----------------------------------------------------------------------

    def process_url(
        self,
        url: str,
        segment_duration: float = 30,
        frame_size: Tuple[int, int] = (320, 180),
        load_as_bytes: bool = True,
        keep_files: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict:
        """一站式处理：下载 -> 元数据 -> 分割 -> 提取首帧 -> 加载字节流"""
        if progress_callback:
            progress_callback("download", 0)

        video_path = self.download_video(url)

        if progress_callback:
            progress_callback("download", 1.0)
            progress_callback("metadata", 0)

        metadata = self.get_metadata(video_path)

        if progress_callback:
            progress_callback("metadata", 1.0)
            progress_callback("split", 0)

        segments = self.split_video(
            video_path=video_path,
            segment_duration=segment_duration,
            frame_size=frame_size,
            load_as_bytes=load_as_bytes,
            keep_files=keep_files,
            extract_first_frame=True,
        )

        if progress_callback:
            progress_callback("split", 1.0)

        if not keep_files:
            try:
                os.remove(video_path)
                self._managed_files.discard(os.path.abspath(video_path))
            except OSError:
                pass

        return {
            "metadata": metadata,
            "segments": segments,
            "total_segments": len(segments),
            "total_duration": metadata.duration,
        }

    # -----------------------------------------------------------------------
    # 字节流工具
    # -----------------------------------------------------------------------

    def get_bytes(self, file_path: str) -> bytes:
        """将文件加载为字节流"""
        with open(file_path, "rb") as f:
            return f.read()

    def bytes_to_file(self, data: bytes, suffix: str = ".mp4") -> str:
        """将字节流写入临时文件"""
        path = self._generate_temp_path(suffix=suffix)
        with open(path, "wb") as f:
            f.write(data)
        return path


# ===========================================================================
# 模块级单例（外部统一入口）
# ===========================================================================
ffmpeg_tool = FFmpegVideoTool()
