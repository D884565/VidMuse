import ffmpeg
import numpy as np
import subprocess
from typing import Dict, Any, Optional, List, Union


class FFmpegVideoProcessor:
    """基于 ffmpeg-python 的高性能视频处理器"""

    def __init__(self, input_source: str):
        """
        初始化处理器
        :param input_source: 本地文件路径或 'pipe:' (用于内存流)
        """
        self.input_source = input_source

    def get_metadata(self) -> Dict[str, Any]:
        """获取视频的元数据信息（分辨率、时长、编码等）"""
        try:
            probe = ffmpeg.probe(self.input_source)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)

            if not video_stream:
                raise ValueError("未找到视频流")

            return {
                "width": int(video_stream['width']),
                "height": int(video_stream['height']),
                "duration": float(probe['format']['duration']),
                "codec": video_stream['codec_name'],
                "fps": eval(video_stream.get('r_frame_rate', '0/1'))
            }
        except ffmpeg.Error as e:
            print(f"FFmpeg Probe Error: {e.stderr.decode()}")
            raise

    def clip(self, output_path: str, start_time: str = None, duration: str = None):
        """
        精准剪辑视频片段
        :param output_path: 输出文件路径
        :param start_time: 起始时间，格式 'HH:MM:SS' 或纯秒数
        :param duration: 持续时长，格式 'HH:MM:SS' 或纯秒数
        """
        try:
            input_kwargs = {}
            output_kwargs = {'c': 'copy'}  # 默认使用无损流复制，速度极快

            if start_time:
                input_kwargs['ss'] = start_time
            if duration:
                output_kwargs['t'] = duration

            (
                ffmpeg
                .input(self.input_source, **input_kwargs)
                .output(output_path, **output_kwargs)
                .overwrite_output()
                .run()
            )
            print(f"剪辑成功: {output_path}")
        except ffmpeg.Error as e:
            print(f"FFmpeg Clip Error: {e.stderr.decode()}")

    def extract_audio(self, output_path: str, audio_codec: str = 'mp3'):
        """提取音频"""
        try:
            (
                ffmpeg
                .input(self.input_source)
                .output(output_path, acodec=audio_codec, vn=None)  # vn=None 表示禁用视频流
                .overwrite_output()
                .run()
            )
            print(f"音频提取成功: {output_path}")
        except ffmpeg.Error as e:
            print(f"FFmpeg Audio Extract Error: {e.stderr.decode()}")

    def read_frame_as_array(self, frame_num: int, fps: float = 25.0) -> np.ndarray:
        """
        利用管道直接读取特定帧到 numpy 数组（无磁盘交互，适合AI模型推理前处理）
        :param frame_num: 目标帧序号
        :param fps: 视频帧率
        """
        meta = self.get_metadata()
        width, height = meta['width'], meta['height']

        out, _ = (
            ffmpeg
            .input(self.input_source, ss=frame_num / fps)
            .filter('scale', width, height)
            .output('pipe:', format='rawvideo', pix_fmt='rgb24', vframes=1)
            .run(capture_stdout=True, capture_stderr=True)
        )
        return np.frombuffer(out, np.uint8).reshape([height, width, 3])

    @staticmethod
    def probe_in_memory(video_bytes: bytes) -> Dict[str, Any]:
        """
        【新增】直接从内存字节流中解析视频元数据
        :param video_bytes: 完整的视频二进制数据 (bytes)
        """
        try:
            # 关键：将 bytes 通过 input 参数传给 pipe:
            probe = ffmpeg.probe('pipe:', input=video_bytes, probesize='10M')

            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if not video_stream:
                raise ValueError("内存流中未找到视频流")

            return {
                "width": int(video_stream['width']),
                "height": int(video_stream['height']),
                "duration": float(probe['format']['duration']),
                "codec": video_stream['codec_name'],
                "fps": eval(video_stream.get('r_frame_rate', '0/1'))
            }
        except ffmpeg.Error as e:
            print(f"FFmpeg Memory Probe Error: {e.stderr.decode()}")
            raise


    @staticmethod
    def clip_in_memory(video_bytes: bytes,start_time: str = None, duration: str = None) -> bytes:
        """
        【纯内存剪辑】从内存读取，剪辑后直接在内存中返回 bytes，不落盘
        """
        try:
            input_kwargs = {}
            output_kwargs = {'c': 'copy', 'format': 'mp4'}  # 必须指定 format

            if start_time:
                input_kwargs['ss'] = start_time
            if duration:
                output_kwargs['t'] = duration

            # 注意：output 使用 'pipe:'，并设置 capture_stdout=True
            out, _ = (
                ffmpeg
                .input('pipe:', **input_kwargs)
                .output('pipe:', **output_kwargs)
                .run(input=video_bytes, capture_stdout=True, capture_stderr=True)
            )
            return out
        except ffmpeg.Error as e:
            print(f"FFmpeg Memory-to-Memory Clip Error: {e.stderr.decode()}")
            raise


    @staticmethod
    def stream_clip_in_memory(file_stream, output_path: str,
                    start_time: str = None, duration: str = None, chunk_size: int = 8192):
        """
        【流式剪辑】适合超大视频文件（如对象存储直连），边下载边剪辑，极低内存占用
        :param file_stream: 具备 read() 方法的流对象 (如 OSS/MinIO 返回的 response)
        :param output_path: 剪辑后的输出文件路径
        :param start_time: 起始时间 ('HH:MM:SS' 或秒数)
        :param duration: 持续时长 ('HH:MM:SS' 或秒数)
        :param chunk_size: 每次从网络读取的字节大小，默认 8KB
        """
        command = ['ffmpeg', '-y']

        # 拼接输入参数
        if start_time:
            command.extend(['-ss', str(start_time)])
        command.extend(['-i', 'pipe:0'])

        # 拼接输出参数
        command.extend(['-c', 'copy'])
        if duration:
            command.extend(['-t', str(duration)])
        command.append(output_path)

        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            # 核心逻辑：分块读取网络流，实时写入 FFmpeg 的 stdin
            while True:
                chunk = file_stream.read(chunk_size)
                if not chunk:
                    break
                process.stdin.write(chunk)

        finally:
            # 确保无论是否发生异常，都能正确关闭资源
            if hasattr(file_stream, 'close'):
                file_stream.close()
            if hasattr(file_stream, 'release_conn'):
                file_stream.release_conn()

            process.stdin.close()
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                print(f"FFmpeg Stream Clip Failed: {stderr.decode()}")
                raise RuntimeError("Stream clipping failed.")
            else:
                print(f"流式剪辑成功: {output_path}")

    @staticmethod
    def _calculate_optimal_segments(total_duration: float, segment_duration_range: tuple = (4, 5)) -> tuple[int, float]:
        """
        【内部辅助方法】计算最佳分割段数和每段时长
        :param total_duration: 视频总时长
        :param segment_duration_range: 片段时长范围
        :return: (最佳段数, 每段时长)
        """
        if total_duration <= 0:
            raise ValueError("视频时长无效")

        min_duration, max_duration = segment_duration_range

        # 计算最合适的段数，使得每段时长在min_duration和max_duration之间
        # 优先选择更接近max_duration的段数，以减少段数
        min_segments = int(total_duration / max_duration)
        max_segments = int(total_duration / min_duration)

        # 确保至少有1段
        min_segments = max(min_segments, 1)
        max_segments = max(max_segments, 1)

        # 寻找最佳段数：优先选择能让每段时长尽可能接近max_duration的段数
        best_segments = max_segments
        best_duration = total_duration / best_segments

        # 检查是否有更优的段数
        for n in range(min_segments, max_segments + 1):
            current_duration = total_duration / n
            # 如果当前时长在范围内，并且比最佳时长更长（更接近max_duration）
            if min_duration <= current_duration <= max_duration and current_duration > best_duration:
                best_duration = current_duration
                best_segments = n

        # 确保最佳时长在范围内
        if not (min_duration <= best_duration <= max_duration):
            # 如果没有完美匹配，选择最接近的段数
            best_segments = round(total_duration / ((min_duration + max_duration) / 2))
            best_segments = max(best_segments, 1)
            best_duration = total_duration / best_segments

        return best_segments, best_duration

    def split_into_segments(self, output_dir: str, segment_duration_range: tuple = (4, 5),
                           output_prefix: str = "segment_",
                           extract_first_frame: bool = False,
                           frame_output_dir: Optional[str] = None,
                           frame_format: str = 'png',
                           frame_quality: int = 2,
                           frame_prefix: Optional[str] = None) -> Union[List[str], List[Dict[str, str]]]:
        """
        将视频分割为时长相等的片段，每段时长在指定范围内
        :param output_dir: 输出目录（需要提前创建）
        :param segment_duration_range: 片段时长范围，默认(4,5)秒
        :param output_prefix: 输出文件前缀
        :param extract_first_frame: 是否提取每个片段的首帧，默认False
        :param frame_output_dir: 首帧输出目录，默认与视频输出目录相同
        :param frame_format: 首帧格式，默认png
        :param frame_quality: 首帧质量，1-31越小越好，默认2
        :param frame_prefix: 首帧文件名前缀，默认与视频前缀相同
        :return: 如果不提取首帧返回视频路径列表；如果提取首帧返回字典列表，包含video_path和frame_path
        """
        import os

        # 获取视频元数据
        metadata = self.get_metadata()
        total_duration = metadata['duration']

        # 计算最佳分割参数
        best_segments, best_duration = self._calculate_optimal_segments(total_duration, segment_duration_range)
        print(f"视频总时长: {total_duration:.2f}秒，将分割为 {best_segments} 段，每段约 {best_duration:.2f} 秒")

        # 处理首帧输出目录
        if extract_first_frame and frame_output_dir is None:
            frame_output_dir = output_dir
        if extract_first_frame and frame_prefix is None:
            frame_prefix = output_prefix

        # 确保目录存在
        os.makedirs(output_dir, exist_ok=True)
        if extract_first_frame:
            os.makedirs(frame_output_dir, exist_ok=True)

        output_results = []

        # 分割视频
        for i in range(best_segments):
            start_time = i * best_duration
            output_path = os.path.join(output_dir, f"{output_prefix}{i:03d}.mp4")

            # 调用现有的clip方法
            self.clip(output_path, start_time=str(start_time), duration=str(best_duration))

            if extract_first_frame:
                # 提取首帧
                frame_path = os.path.join(frame_output_dir, f"{frame_prefix}{i:03d}.{frame_format}")
                self.extract_frame_by_timestamp(
                    start_time,
                    output_path=frame_path,
                    img_format=frame_format,
                    quality=frame_quality
                )
                output_results.append({
                    "segment_index": i,
                    "start_time": start_time,
                    "duration": best_duration,
                    "video_path": output_path,
                    "frame_path": frame_path
                })
            else:
                output_results.append(output_path)

        print(f"视频分割完成，共生成 {len(output_results)} 个片段")
        if extract_first_frame:
            print(f"已同时提取 {len(output_results)} 个首帧到 {frame_output_dir}")

        return output_results

    @staticmethod
    def split_into_segments_in_memory(video_bytes: bytes, segment_duration_range: tuple = (4, 5),
                                     extract_first_frame: bool = False,
                                     frame_output_dir: Optional[str] = None,
                                     frame_format: str = 'png',
                                     frame_quality: int = 2,
                                     frame_prefix: str = "segment_",
                                     return_frame_bytes: bool = True) -> Union[List[bytes], List[Dict[str, Any]]]:
        """
        【纯内存分割】将视频字节流分割为时长相等的片段，不落盘
        :param video_bytes: 输入视频字节流
        :param segment_duration_range: 片段时长范围，默认(4,5)秒
        :param extract_first_frame: 是否提取每个片段的首帧，默认False
        :param frame_output_dir: 首帧输出目录，如果为None则首帧返回内存数据，否则保存到文件
        :param frame_format: 首帧格式，默认png
        :param frame_quality: 首帧质量，1-31越小越好，默认2
        :param frame_prefix: 首帧文件名前缀，默认segment_
        :param return_frame_bytes: 如果为True，返回编码后的图片字节流；如果为False，返回numpy数组（仅当frame_output_dir为None时有效）
        :return: 如果不提取首帧返回视频字节列表；
                 如果提取首帧且frame_output_dir为None:
                     - return_frame_bytes=True时，返回字典列表包含video_bytes和frame_bytes（图片字节流）
                     - return_frame_bytes=False时，返回字典列表包含video_bytes和frame_array（numpy数组）
                 如果提取首帧且frame_output_dir不为None，返回字典列表包含video_bytes和frame_path
        """
        import os
        # 从内存字节流中获取视频元数据
        metadata = FFmpegVideoProcessor.probe_in_memory(video_bytes)
        total_duration = metadata['duration']

        # 计算最佳分割参数
        best_segments, best_duration = FFmpegVideoProcessor._calculate_optimal_segments(
            total_duration, segment_duration_range
        )
        print(f"视频总时长: {total_duration:.2f}秒，将分割为 {best_segments} 段，每段约 {best_duration:.2f} 秒")

        # 如果需要保存帧到文件，确保目录存在
        if extract_first_frame and frame_output_dir is not None:
            os.makedirs(frame_output_dir, exist_ok=True)

        output_results = []

        # 分割视频
        for i in range(best_segments):
            start_time = i * best_duration
            # 调用现有的clip_in_memory静态方法
            segment_bytes = FFmpegVideoProcessor.clip_in_memory(video_bytes, start_time=str(start_time), duration=str(best_duration))

            if extract_first_frame:
                if frame_output_dir is not None:
                    # 保存帧到文件
                    frame_path = os.path.join(frame_output_dir, f"{frame_prefix}{i:03d}.{frame_format}")
                    FFmpegVideoProcessor.extract_frame_by_timestamp_in_memory(
                        video_bytes,
                        start_time,
                        output_path=frame_path,
                        img_format=frame_format,
                        quality=frame_quality
                    )
                    output_results.append({
                        "segment_index": i,
                        "start_time": start_time,
                        "duration": best_duration,
                        "video_bytes": segment_bytes,
                        "frame_path": frame_path
                    })
                else:
                    if return_frame_bytes:
                        # 首帧以编码后的字节流形式返回（PNG/JPG格式）
                        frame_bytes = FFmpegVideoProcessor.extract_frame_by_timestamp_in_memory(
                            video_bytes,
                            start_time,
                            output_path=None,
                            img_format=frame_format,
                            quality=frame_quality,
                            return_encoded_bytes=True
                        )
                        output_results.append({
                            "segment_index": i,
                            "start_time": start_time,
                            "duration": best_duration,
                            "video_bytes": segment_bytes,
                            "frame_bytes": frame_bytes,
                            "frame_format": frame_format
                        })
                    else:
                        # 首帧以numpy数组形式返回
                        frame_array = FFmpegVideoProcessor.extract_frame_by_timestamp_in_memory(
                            video_bytes,
                            start_time,
                            img_format=frame_format,
                            quality=frame_quality,
                            return_encoded_bytes=False
                        )
                        output_results.append({
                            "segment_index": i,
                            "start_time": start_time,
                            "duration": best_duration,
                            "video_bytes": segment_bytes,
                            "frame_array": frame_array
                        })
            else:
                output_results.append(segment_bytes)

        print(f"内存分割完成，共生成 {len(output_results)} 个片段")
        if extract_first_frame:
            if frame_output_dir:
                print(f"已同时提取 {len(output_results)} 个首帧到 {frame_output_dir}")
            else:
                if return_frame_bytes:
                    print(f"已同时提取 {len(output_results)} 个首帧为{frame_format}格式字节流")
                else:
                    print(f"已同时提取 {len(output_results)} 个首帧为numpy数组")

        return output_results

    def extract_frame_by_timestamp(self, timestamp: Union[float, str], output_path: Optional[str] = None,
                                  img_format: str = 'png', quality: int = 2) -> Optional[np.ndarray]:
        """
        根据时间戳提取视频帧
        :param timestamp: 时间戳，可以是秒数（float）或 'HH:MM:SS' 格式字符串
        :param output_path: 输出文件路径，如果为None则返回numpy数组
        :param img_format: 输出格式，默认'png'，支持'jpg'、'jpeg'、'png'等
        :param quality: 输出质量，1-31，越小质量越高，默认2
        :return: 如果output_path为None返回numpy数组，否则返回None
        """
        import os
        try:
            # 获取视频元数据
            meta = self.get_metadata()
            width, height = meta['width'], meta['height']

            if output_path:
                # 输出到文件
                # 处理路径：如果是目录则自动生成文件名
                if os.path.isdir(output_path):
                    # 目录情况下，自动生成文件名
                    timestamp_str = str(timestamp).replace(':', '-').replace('.', '_')
                    output_path = os.path.join(output_path, f"frame_{timestamp_str}.{img_format}")
                else:
                    # 检查是否有扩展名，如果没有则添加
                    ext = os.path.splitext(output_path)[1].lower()
                    if not ext:
                        output_path = f"{output_path}.{img_format}"
                    else:
                        # 从扩展名推断格式
                        ext = ext.lstrip('.')
                        if ext in ['jpg', 'jpeg', 'png']:
                            img_format = ext

                # 确保输出目录存在
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

                # 输出图片时不需要指定format，ffmpeg会自动从扩展名识别
                # 对于单帧输出，使用image2 muxer
                output_kwargs = {'vframes': 1, 'q:v': quality}
                if img_format:
                    # 如果指定了format，使用正确的muxer名称
                    output_kwargs['format'] = 'image2'
                    # 对于jpg/jpeg需要额外指定编码器
                    if img_format.lower() in ['jpg', 'jpeg']:
                        output_kwargs['vcodec'] = 'mjpeg'

                (
                    ffmpeg
                    .input(self.input_source, ss=timestamp)
                    .output(output_path, **output_kwargs)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                print(f"帧提取成功: {output_path}")
                return None
            else:
                # 输出到内存numpy数组
                out, _ = (
                    ffmpeg
                    .input(self.input_source, ss=timestamp)
                    .filter('scale', width, height)
                    .output('pipe:', format='rawvideo', pix_fmt='rgb24', vframes=1)
                    .run(capture_stdout=True, capture_stderr=True)
                )
                return np.frombuffer(out, np.uint8).reshape([height, width, 3])

        except ffmpeg.Error as e:
            print(f"FFmpeg Frame Extract Error: {e.stderr.decode()}")
            raise

    @staticmethod
    def extract_frame_by_timestamp_in_memory(video_bytes: bytes, timestamp: Union[float, str],
                                            output_path: Optional[str] = None,
                                            img_format: str = 'png', quality: int = 2,
                                            return_encoded_bytes: bool = False) -> Union[Optional[np.ndarray], bytes, None]:
        """
        【纯内存版本】根据时间戳从视频字节流中提取帧
        :param video_bytes: 输入视频字节流
        :param timestamp: 时间戳，可以是秒数（float）或 'HH:MM:SS' 格式字符串
        :param output_path: 输出文件路径，如果为None则根据return_encoded_bytes参数返回对应数据
        :param img_format: 输出格式，默认'png'，支持'jpg'、'jpeg'、'png'等
        :param quality: 输出质量，1-31，越小质量越高，默认2
        :param return_encoded_bytes: 如果为True，返回编码后的图片字节流（PNG/JPG格式）；如果为False，返回numpy数组
        :return:
            - output_path不为None时：返回None
            - output_path为None且return_encoded_bytes为False时：返回numpy数组（RGB格式）
            - output_path为None且return_encoded_bytes为True时：返回bytes（编码后的图片二进制数据）
        """
        import os
        try:
            if output_path:
                # 输出到文件
                # 处理路径：如果是目录则自动生成文件名
                if os.path.isdir(output_path):
                    # 目录情况下，自动生成文件名
                    timestamp_str = str(timestamp).replace(':', '-').replace('.', '_')
                    output_path = os.path.join(output_path, f"frame_{timestamp_str}.{img_format}")
                else:
                    # 检查是否有扩展名，如果没有则添加
                    ext = os.path.splitext(output_path)[1].lower()
                    if not ext:
                        output_path = f"{output_path}.{img_format}"
                    else:
                        # 从扩展名推断格式
                        ext = ext.lstrip('.')
                        if ext in ['jpg', 'jpeg', 'png']:
                            img_format = ext

                # 确保输出目录存在
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

                # 输出图片时不需要指定format，ffmpeg会自动从扩展名识别
                # 对于单帧输出，使用image2 muxer
                output_kwargs = {'vframes': 1, 'q:v': quality}
                if img_format:
                    # 如果指定了format，使用正确的muxer名称
                    output_kwargs['format'] = 'image2'
                    # 对于jpg/jpeg需要额外指定编码器
                    if img_format.lower() in ['jpg', 'jpeg']:
                        output_kwargs['vcodec'] = 'mjpeg'

                (
                    ffmpeg
                    .input('pipe:', ss=timestamp)
                    .output(output_path, **output_kwargs)
                    .overwrite_output()
                    .run(input=video_bytes, capture_stdout=True, capture_stderr=True)
                )
                print(f"内存帧提取成功: {output_path}")
                return None
            else:
                if return_encoded_bytes:
                    # 返回编码后的图片字节流（PNG/JPG格式）
                    output_kwargs = {'vframes': 1, 'q:v': quality, 'format': 'image2'}

                    # 根据格式明确指定编码器
                    if img_format.lower() in ['jpg', 'jpeg']:
                        output_kwargs['vcodec'] = 'mjpeg'
                    else:  # png
                        output_kwargs['vcodec'] = 'png'

                    out, _ = (
                        ffmpeg
                        .input('pipe:', ss=timestamp)
                        .output('pipe:', **output_kwargs)
                        .run(input=video_bytes, capture_stdout=True, capture_stderr=True)
                    )
                    return out  # 直接返回编码后的字节流
                else:
                    # 输出到内存numpy数组
                    meta = FFmpegVideoProcessor.probe_in_memory(video_bytes)
                    width, height = meta['width'], meta['height']
                    out, _ = (
                        ffmpeg
                        .input('pipe:', ss=timestamp)
                        .filter('scale', width, height)
                        .output('pipe:', format='rawvideo', pix_fmt='rgb24', vframes=1)
                        .run(input=video_bytes, capture_stdout=True, capture_stderr=True)
                    )
                    return np.frombuffer(out, np.uint8).reshape([height, width, 3])

        except ffmpeg.Error as e:
            print(f"FFmpeg Memory Frame Extract Error: {e.stderr.decode()}")
            raise


