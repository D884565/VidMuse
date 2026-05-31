import subprocess
import json
import os
import re
import shutil
import tempfile
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse
import threading
import time


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


class FFmpegVideoTool:
    """
    FFmpeg 视频处理工具类

    功能：
    1. 从 URL 下载视频
    2. 获取视频元数据
    3. 按指定时间段分割视频
    4. 提取每段首帧
    5. 将结果加载为内存字节流
    6. 自动清理临时文件
    """

    def __init__(
            self,
            ffmpeg_path: str = "ffmpeg",
            ffprobe_path: str = "ffprobe",
            temp_dir: Optional[str] = None,
            auto_cleanup: bool = True,
            chunk_size: int = 8192
    ):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path
        self.chunk_size = chunk_size
        self.auto_cleanup = auto_cleanup

        # 创建临时目录
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="ffmpeg_tool_")
        os.makedirs(self.temp_dir, exist_ok=True)

        # 跟踪所有创建的文件用于清理
        self._managed_files: set = set()
        self._lock = threading.Lock()

        self._validate_tools()

    def __del__(self):
        """析构时自动清理"""
        if self.auto_cleanup:
            self.cleanup()

    def _validate_tools(self):
        """验证 FFmpeg 工具"""
        for tool in [self.ffmpeg, self.ffprobe]:
            try:
                result = subprocess.run([tool, "-version"], capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    raise RuntimeError(f"{tool} 返回错误")
            except FileNotFoundError:
                raise RuntimeError(f"未找到 {tool}，请确保 FFmpeg 已安装")

    def _run_command(self, cmd: List[str], timeout: Optional[int] = None, cwd: Optional[str] = None) -> Tuple[
        int, str, str]:
        """执行命令"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding='utf-8',
                                    errors='ignore', cwd=cwd)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timeout"
        except Exception as e:
            return -1, "", str(e)

    def _track_file(self, path: str):
        """跟踪文件以便清理"""
        with self._lock:
            self._managed_files.add(os.path.abspath(path))

    def _generate_temp_path(self, suffix: str = "", prefix: str = "tmp") -> str:
        """生成临时文件路径"""
        name = f"{prefix}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}{suffix}"
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
                except Exception:
                    pass
            self._managed_files.clear()

            # 清理临时目录（如果是内部创建的）
            try:
                if os.path.exists(self.temp_dir) and not os.listdir(self.temp_dir):
                    os.rmdir(self.temp_dir)
            except Exception:
                pass

    # ==================== 下载功能 ====================

    def download_video(
            self,
            url: str,
            output_path: Optional[str] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: int = 300,
            progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        下载视频文件

        支持方式：
        1. HTTP/HTTPS URL：使用 ffmpeg 或 requests 下载
        2. 本地路径：直接复制到临时目录

        Args:
            url: 视频 URL 或本地路径
            output_path: 指定输出路径，None 则自动生成
            headers: HTTP 请求头
            timeout: 下载超时（秒）
            progress_callback: 进度回调(bytes_downloaded, total_bytes)

        Returns:
            下载后的本地文件路径
        """
        # 本地文件直接处理
        if os.path.isfile(url):
            if output_path:
                shutil.copy2(url, output_path)
                self._track_file(output_path)
                return output_path
            return url  # 直接返回原路径，不复制

        # 生成输出路径
        if output_path is None:
            # 从 URL 提取扩展名
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1] or ".mp4"
            output_path = self._generate_temp_path(suffix=ext, prefix="download")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # 优先使用 ffmpeg 下载（支持更多协议和格式）
        cmd = [self.ffmpeg, "-y"]

        if headers:
            for key, value in headers.items():
                cmd.extend(["-headers", f"{key}: {value}"])

        cmd.extend([
            "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
            "-i", url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",  # 处理 HLS 流
            output_path
        ])

        # ffmpeg 下载不直接支持进度回调，使用简单方式
        returncode, _, stderr = self._run_command(cmd, timeout=timeout)

        if returncode != 0:
            # ffmpeg 下载失败，尝试使用 urllib
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
            progress_callback: Optional[Callable[[int, int], None]]
    ):
        """使用 urllib 下载（备用方案）"""
        import urllib.request

        req = urllib.request.Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=timeout) as response:
            total = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(output_path, 'wb') as f:
                while True:
                    chunk = response.read(self.chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

    # ==================== 元数据 ====================

    def get_metadata(self, video_path: str) -> VideoMetadata:
        """获取视频元数据"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        cmd = [self.ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]
        returncode, stdout, stderr = self._run_command(cmd, timeout=30)

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
        fps = eval(fps_str) if "/" in fps_str else float(fps_str)

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
            sample_rate=int(audio_stream["sample_rate"]) if audio_stream and audio_stream.get("sample_rate") else None
        )

    # ==================== 首帧提取 ====================

    def extract_first_frame(
            self,
            video_path: str,
            output_path: str,
            timestamp: float = 0,
            width: Optional[int] = None,
            height: Optional[int] = None
    ) -> str:
        """提取指定时间点帧"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        filters = []
        if width and height:
            filters.append(
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")
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

    # ==================== 核心分割功能 ====================

    def split_video(
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
            keep_files: bool = False
    ) -> List[SegmentResult]:
        """
        分割视频，可选加载为字节流

        Args:
            video_path: 输入视频路径（本地或 URL）
            output_dir: 输出目录，None 则使用临时目录
            load_as_bytes: 是否将结果加载为内存字节流
            keep_files: 是否保留磁盘文件（即使 load_as_bytes=True）

        Returns:
            List[SegmentResult]，如果 load_as_bytes=True 则包含 segment_bytes 和 frame_bytes
        """
        # 如果是 URL，先下载
        actual_path = video_path
        downloaded = False
        if video_path.startswith(("http://", "https://", "ftp://")):
            actual_path = self.download_video(video_path)
            downloaded = True

        if not os.path.exists(actual_path):
            raise FileNotFoundError(f"视频文件不存在: {actual_path}")

        # 确定输出目录
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

            # 分割命令
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
                    self.extract_first_frame(seg_path, frame_path, 0,
                                             width=frame_size[0] if frame_size else None,
                                             height=frame_size[1] if frame_size else None)
                except Exception as e:
                    frame_path = None

            # 加载字节流
            segment_bytes = None
            frame_bytes = None

            if load_as_bytes:
                if os.path.exists(seg_path):
                    with open(seg_path, 'rb') as f:
                        segment_bytes = f.read()
                if frame_path and os.path.exists(frame_path):
                    with open(frame_path, 'rb') as f:
                        frame_bytes = f.read()

                # 清理文件（如果不保留）
                if not keep_files:
                    try:
                        os.remove(seg_path)
                        self._managed_files.discard(os.path.abspath(seg_path))
                    except:
                        pass
                    if frame_path:
                        try:
                            os.remove(frame_path)
                            self._managed_files.discard(os.path.abspath(frame_path))
                        except:
                            pass

            results.append(SegmentResult(
                segment_path=os.path.abspath(seg_path) if (not load_as_bytes or keep_files) else "",
                first_frame_path=os.path.abspath(frame_path) if (
                            frame_path and (not load_as_bytes or keep_files)) else "",
                start_time=start_time,
                end_time=end_time,
                duration=seg_duration,
                segment_bytes=segment_bytes,
                frame_bytes=frame_bytes
            ))

        # 清理下载的原始文件（如果是临时下载的）
        if downloaded and not keep_files:
            try:
                os.remove(actual_path)
                self._managed_files.discard(os.path.abspath(actual_path))
            except:
                pass

        return results

    # ==================== 便捷方法 ====================

    def process_url(
            self,
            url: str,
            segment_duration: float = 30,
            frame_size: Tuple[int, int] = (320, 180),
            load_as_bytes: bool = True,
            keep_files: bool = False,
            progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Dict:
        """
        一站式处理：下载 -> 获取元数据 -> 分割 -> 提取首帧 -> 加载字节流

        Args:
            url: 视频 URL
            segment_duration: 每段时长（秒）
            frame_size: 首帧尺寸
            load_as_bytes: 是否加载为字节流
            keep_files: 是否保留磁盘文件
            progress_callback: 进度回调(stage, progress)

        Returns:
            {
                "metadata": VideoMetadata,
                "segments": List[SegmentResult],
                "total_segments": int,
                "total_duration": float
            }
        """
        if progress_callback:
            progress_callback("download", 0)

        # 下载
        video_path = self.download_video(url)

        if progress_callback:
            progress_callback("download", 1.0)
            progress_callback("metadata", 0)

        # 获取元数据
        metadata = self.get_metadata(video_path)

        if progress_callback:
            progress_callback("metadata", 1.0)
            progress_callback("split", 0)

        # 分割
        segments = self.split_video(
            video_path=video_path,
            segment_duration=segment_duration,
            frame_size=frame_size,
            load_as_bytes=load_as_bytes,
            keep_files=keep_files,
            extract_first_frame=True
        )

        if progress_callback:
            progress_callback("split", 1.0)

        # 清理
        if not keep_files:
            try:
                os.remove(video_path)
                self._managed_files.discard(os.path.abspath(video_path))
            except:
                pass

        return {
            "metadata": metadata,
            "segments": segments,
            "total_segments": len(segments),
            "total_duration": metadata.duration
        }

    def get_bytes(self, file_path: str) -> bytes:
        """将文件加载为字节流"""
        with open(file_path, 'rb') as f:
            return f.read()

    def bytes_to_file(self, data: bytes, suffix: str = ".mp4") -> str:
        """将字节流写入临时文件"""
        path = self._generate_temp_path(suffix=suffix)
        with open(path, 'wb') as f:
            f.write(data)
        return path


