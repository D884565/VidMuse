import asyncio
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple
import logging

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
from backend.providers import VolcanoLLM, VideoUnderstandingResponse
from backend.providers.dto.schema import VideoUnderstandingRequest, ImageUrlContent, TextContent, MultimodalContent
from backend.v1.app.pipeline.utils import prompt_manager, JsonFlattener
from backend.ffmpeg.pyutils import ffmpeg_tool
from backend.v1.app.pipeline.processors.audio.audio_asr_processor import AudioASRProcessor
from backend.store import get_storage_client
from backend.v1.app.config.config import settings

logger = logging.getLogger(__name__)


class VideoKeyframeAudioUnderstandingProcessor(BaseProcessor):
    """
    基于关键帧和音频识别的视频理解处理器（用于AB测试）
    流程：视频下载 → 场景变化关键帧抽取 → 音频提取 → ASR语音识别 → 关键帧+对应文本发送给大模型 → 输出与原理解处理器完全兼容的结果
    """

    def __init__(self, llm_client=None, scene_threshold: float = 0.3, max_keyframes: int = 20, min_keyframes: int = 3):
        """
        初始化处理器

        :param llm_client: 大模型客户端，默认使用VolcanoLLM
        :param scene_threshold: 场景变化检测阈值，0-1之间，越大越严格，关键帧越少
        :param max_keyframes: 最大关键帧数量，避免过多关键帧导致成本过高
        :param min_keyframes: 最小关键帧数量，避免过短视频内容过少
        """
        self.llm_client = llm_client or VolcanoLLM(key=None, model_name=None)
        self.prompt_template = prompt_manager.get_slice_understanding_prompt()
        self.scene_threshold = scene_threshold
        self.max_keyframes = max_keyframes
        self.min_keyframes = min_keyframes
        self.asr_processor = AudioASRProcessor()
        self.storage_client = get_storage_client()

    def run_async(self, coro):
        """万能异步运行器，兼容所有环境"""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # 已有循环在跑，用线程池避免冲突
                with ThreadPoolExecutor(max_workers=1) as executor:
                    return executor.submit(
                        lambda: asyncio.run(coro)
                    ).result()
        except RuntimeError:
            pass

        # 没有运行中的循环，直接 run
        return asyncio.run(coro)

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频理解逻辑

        输入（从上下文获取）：
        - slices_url: List[str] 视频分片URL列表（仅使用第一个分片，即完整视频URL）
        - video_id: str 视频ID（初始输入）

        输出（写入上下文）：
        - understood_slices: List[Dict] 理解后的分片结构化数据，与原处理器格式完全一致
        - embed_slices: List[Dict] 扁平化后的分片数据，用于向量化，与原处理器格式完全一致
        """
        # 从上下文获取视频数据
        slices_url = context.get(constants.SLICES_URL, [])
        video_id = context.get(constants.VIDEO_ID)

        if not slices_url:
            raise ValueError("No video URL found in context")

        # 第一个分片就是完整视频（因为AB测试版本不做视频分片，直接处理完整视频）
        video_url = slices_url[0]

        try:
            # 1. 下载视频到临时文件
            video_path = ffmpeg_tool.download_video(video_url)
            logger.info(f"视频下载完成: {video_path}")

            # 2. 基于场景变化抽取关键帧
            keyframes = self._extract_keyframes(video_path, video_id)
            logger.info(f"抽取关键帧完成，共 {len(keyframes)} 个关键帧")

            if not keyframes:
                raise ValueError("未抽取到任何关键帧")

            # 3. 提取音频并进行ASR识别
            asr_result = self._extract_and_recognize_audio(video_path, video_id)
            logger.info(f"音频识别完成，文本长度: {len(asr_result.get('transcript', ''))}")

            # 4. 将ASR文本按关键帧时间段分段
            segmented_texts = self._segment_asr_result(asr_result, keyframes)
            logger.info(f"文本分段完成，共 {len(segmented_texts)} 段")

            # 5. 每个关键帧+对应文本调用大模型理解
            understood_slices = []
            embed_slices = []

            for i, (keyframe, text) in enumerate(zip(keyframes, segmented_texts)):
                try:
                    # 构建多模态输入：关键帧图片 + 对应文本
                    understanding_result = self._understand_keyframe(
                        keyframe["url"],
                        text,
                        keyframe["start_time"],
                        keyframe["end_time"]
                    )

                    # 构建与原处理器完全一致的分片数据结构
                    slice_data = {
                        "slice_id": f"{video_id}_slice_{i}",
                        "video_id": video_id,
                        "slice_index": i,
                        "slice_url": video_url,  # 使用原视频URL
                        "cover_url": keyframe["url"],
                        "slice_object_name": "",  # 不需要分片对象名
                        "cover_object_name": keyframe["object_name"],
                        "understanding": understanding_result
                    }

                    understood_slices.append(slice_data)

                    # 准备向量化数据，与原处理器格式完全一致
                    understanding_with_id = understanding_result.copy()
                    understanding_with_id["slice_id"] = slice_data["slice_id"]
                    understanding_with_id["video_id"] = video_id
                    flattened = JsonFlattener.flatten(understanding_with_id)

                    embed_data = {
                        "slice_id": slice_data["slice_id"],
                        "content": flattened,
                        "start_time": float(keyframe["start_time"]),
                        "end_time": float(keyframe["end_time"])
                    }
                    embed_slices.append(embed_data)

                except Exception as e:
                    logger.error(f"关键帧 {i} 理解失败: {str(e)}", exc_info=True)
                    context.add_error(ValueError(f"关键帧 {i} 理解失败: {str(e)}"))
                    continue

            # 存储结果到上下文，与原处理器格式完全一致
            context.set(constants.UNDERSTOOD_SLICES, understood_slices)
            context.set(constants.EMBED_SLICES, embed_slices)
            context.set(constants.SLICE_COVER_URLS, [kf["url"] for kf in keyframes])

            logger.info(f"视频理解完成，共生成 {len(understood_slices)} 个有效分片")

            # 清理临时文件
            self._cleanup_temp_files(video_path, keyframes)

            return context

        except Exception as e:
            logger.error(f"视频理解流程失败: {str(e)}", exc_info=True)
            context.add_error(ValueError(f"视频理解失败: {str(e)}"))
            return context

    def _extract_keyframes(self, video_path: str, video_id: str) -> List[Dict]:
        """
        基于场景变化抽取关键帧

        :param video_path: 本地视频文件路径
        :param video_id: 视频ID
        :return: 关键帧列表，包含url、object_name、start_time、end_time
        """
        # 获取视频时长
        metadata = ffmpeg_tool.get_metadata(video_path)
        duration = metadata.duration

        if duration <= 0:
            raise ValueError(f"无法获取视频时长: {video_path}")

        # 创建临时目录存放关键帧
        with tempfile.TemporaryDirectory() as temp_dir:
            # 使用FFmpeg场景变化检测抽取关键帧
            output_pattern = os.path.join(temp_dir, f"keyframe_%04d.jpg")

            cmd = [
                ffmpeg_tool.ffmpeg,
                "-y",
                "-i", video_path,
                "-vf", f"select='gt(scene,{self.scene_threshold})',showinfo",
                "-vsync", "vfr",
                "-q:v", "2",
                output_pattern
            ]

            try:
                returncode, stdout, stderr = ffmpeg_tool._run_command(cmd, timeout=120)
                if returncode != 0:
                    # 如果场景检测失败，回退到固定间隔抽取
                    logger.warning(f"场景变化检测失败，回退到固定间隔抽取: {stderr}")
                    return self._extract_keyframes_fixed_interval(video_path, video_id, duration)
            except Exception as e:
                logger.warning(f"场景变化检测异常，回退到固定间隔抽取: {str(e)}")
                return self._extract_keyframes_fixed_interval(video_path, video_id, duration)

            # 解析输出获取关键帧时间戳
            keyframe_times = []
            for line in stderr.split('\n'):
                if "showinfo" in line and "pts_time:" in line:
                    try:
                        time_str = line.split("pts_time:")[1].split()[0]
                        keyframe_time = float(time_str)
                        keyframe_times.append(keyframe_time)
                    except (IndexError, ValueError):
                        continue

            # 去重并排序
            keyframe_times = sorted(list(set(keyframe_times)))

            # 控制关键帧数量
            if len(keyframe_times) > self.max_keyframes:
                # 数量过多，均匀采样
                step = len(keyframe_times) // self.max_keyframes
                keyframe_times = keyframe_times[::step][:self.max_keyframes]
            elif len(keyframe_times) < self.min_keyframes:
                # 数量过少，补充固定间隔的关键帧
                fixed_times = [i * duration / self.min_keyframes for i in range(self.min_keyframes)]
                keyframe_times = sorted(list(set(keyframe_times + fixed_times)))[:self.max_keyframes]

            # 添加结束时间
            keyframe_info = []
            for i, time in enumerate(keyframe_times):
                end_time = keyframe_times[i + 1] if i < len(keyframe_times) - 1 else duration
                keyframe_info.append({
                    "time": time,
                    "start_time": time,
                    "end_time": end_time,
                    "index": i
                })

            # 读取生成的关键帧文件并上传到对象存储
            keyframe_files = sorted([f for f in os.listdir(temp_dir) if f.startswith("keyframe_") and f.endswith(".jpg")])

            result = []
            for i, (kf_info, kf_file) in enumerate(zip(keyframe_info, keyframe_files)):
                kf_path = os.path.join(temp_dir, kf_file)
                if not os.path.exists(kf_path):
                    continue

                # 上传到对象存储
                object_name = f"video_keyframes/{video_id}/{os.path.basename(kf_file)}"
                with open(kf_path, "rb") as f:
                    self.storage_client.upload_fileobj(f, object_name)

                # 获取访问URL
                url = self.storage_client.get_presigned_url(object_name, expires_in=86400 * 30)  # 30天有效期

                result.append({
                    "url": url,
                    "object_name": object_name,
                    "start_time": kf_info["start_time"],
                    "end_time": kf_info["end_time"],
                    "index": i
                })

            return result

    def _extract_keyframes_fixed_interval(self, video_path: str, video_id: str, duration: float) -> List[Dict]:
        """
        固定间隔抽取关键帧（备选方案）
        """
        # 根据视频时长决定抽取数量
        if duration < 30:
            interval = 3  # 30秒以内，3秒一帧
        elif duration < 300:
            interval = 5  # 5分钟以内，5秒一帧
        else:
            interval = 10  # 5分钟以上，10秒一帧

        num_frames = min(self.max_keyframes, max(self.min_keyframes, int(duration / interval)))

        # 使用split_video_segments抽取固定间隔的首帧
        segments = ffmpeg_tool.split_video(
            video_path=video_path,
            segment_count=num_frames,
            extract_first_frame=True,
            frame_format="jpg",
            load_as_bytes=False,
            keep_files=True
        )

        result = []
        for i, seg in enumerate(segments):
            if not seg.first_frame_path or not os.path.exists(seg.first_frame_path):
                continue

            # 上传到对象存储
            object_name = f"video_keyframes/{video_id}/keyframe_{i:04d}.jpg"
            with open(seg.first_frame_path, "rb") as f:
                self.storage_client.upload_fileobj(f, object_name)

            # 获取访问URL
            url = self.storage_client.get_presigned_url(object_name, expires_in=86400 * 30)

            result.append({
                "url": url,
                "object_name": object_name,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "index": i
            })

            # 清理临时文件
            try:
                if os.path.exists(seg.segment_path):
                    os.remove(seg.segment_path)
                if os.path.exists(seg.first_frame_path):
                    os.remove(seg.first_frame_path)
            except OSError:
                pass

        return result

    def _extract_and_recognize_audio(self, video_path: str, video_id: str) -> Dict:
        """
        从视频中提取音频并进行ASR识别

        :param video_path: 本地视频文件路径
        :param video_id: 视频ID
        :return: ASR识别结果，包含transcript、language、speakers、word_timestamps
        """
        # 提取音频到临时文件
        audio_path = tempfile.mktemp(suffix=".mp3", prefix=f"audio_{video_id}_")

        try:
            # 使用FFmpeg提取音频
            cmd = [
                ffmpeg_tool.ffmpeg,
                "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "libmp3lame",
                "-ab", "128k",
                "-ar", "44100",
                "-ac", "1",
                audio_path
            ]

            ffmpeg_tool._run_checked(cmd, timeout=60)
            logger.info(f"音频提取完成: {audio_path}")

            # 上传音频到对象存储
            audio_object_name = f"video_audio/{video_id}/audio.mp3"
            with open(audio_path, "rb") as f:
                self.storage_client.upload_fileobj(f, audio_object_name)

            # 创建临时上下文调用ASR处理器
            asr_context = PipelineContext()
            asr_context.data["object_name"] = audio_object_name

            # 调用ASR处理器
            result_context = self.asr_processor.process(asr_context)

            # 获取识别结果
            asr_result = {
                "transcript": result_context.data.get("transcript", ""),
                "language": result_context.data.get("language", "zh-CN"),
                "speakers": result_context.data.get("speakers", []),
                "word_timestamps": result_context.data.get("word_timestamps", [])
            }

            # 清理音频文件和对象存储
            try:
                os.remove(audio_path)
                self.storage_client.delete_file(audio_object_name)
            except Exception as e:
                logger.warning(f"清理临时音频文件失败: {str(e)}")

            return asr_result

        except Exception as e:
            logger.error(f"音频提取或识别失败: {str(e)}", exc_info=True)
            # 失败时返回默认值，不阻断流程
            return {
                "transcript": "",
                "language": "unknown",
                "speakers": [],
                "word_timestamps": []
            }

    def _segment_asr_result(self, asr_result: Dict, keyframes: List[Dict]) -> List[str]:
        """
        将ASR识别结果按关键帧时间段分段

        :param asr_result: ASR识别结果
        :param keyframes: 关键帧列表
        :return: 每个关键帧对应的文本列表
        """
        full_transcript = asr_result.get("transcript", "")
        word_timestamps = asr_result.get("word_timestamps", [])

        # 如果没有时间戳，按关键帧数量平均分段
        if not word_timestamps or not isinstance(word_timestamps, list):
            words = full_transcript.split()
            if not words:
                return [""] * len(keyframes)

            words_per_segment = max(1, len(words) // len(keyframes))
            segments = []
            for i in range(len(keyframes)):
                start_idx = i * words_per_segment
                end_idx = start_idx + words_per_segment if i < len(keyframes) - 1 else len(words)
                segments.append(" ".join(words[start_idx:end_idx]))
            return segments

        # 有时间戳的情况，按时间段匹配
        segments = []
        for kf in keyframes:
            start_time = kf["start_time"]
            end_time = kf["end_time"]

            # 收集该时间段内的词汇
            segment_words = []
            for word_info in word_timestamps:
                word_start = word_info.get("start_time", 0)
                word_end = word_info.get("end_time", 0)
                # 只要有重叠就包含
                if (word_start >= start_time and word_start < end_time) or \
                   (word_end > start_time and word_end <= end_time) or \
                   (word_start <= start_time and word_end >= end_time):
                    segment_words.append(word_info.get("word", ""))

            segments.append("".join(segment_words))

        return segments

    def _understand_keyframe(self, image_url: str, text: str, start_time: float, end_time: float) -> Dict:
        """
        调用大模型理解单个关键帧和对应文本

        :param image_url: 关键帧图片URL
        :param text: 对应时间段的文本内容
        :param start_time: 片段开始时间
        :param end_time: 片段结束时间
        :return: 理解结果，与原VideoUnderstandingProcessor输出格式完全一致
        """
        # 构建多模态内容
        content = MultimodalContent(content=[
            ImageUrlContent(image_url=image_url),
            TextContent(text=f"视频片段时间：{start_time:.1f}秒 - {end_time:.1f}秒\n对应语音内容：{text}\n请按照要求分析这个视频片段：{self.prompt_template}")
        ])

        # 调用大模型
        try:
            if hasattr(self.llm_client, 'multimodal_understanding') and callable(self.llm_client.multimodal_understanding):
                # 支持多模态接口
                response = self.run_async(self.llm_client.multimodal_understanding(
                    content=content,
                    max_tokens=8192,
                    temperature=0.7,
                    top_p=0.9
                ))
            else:
                # 回退到文本接口，只传文本
                logger.warning("大模型不支持多模态，仅使用文本内容进行理解")
                response = self.run_async(self.llm_client.video_understanding(VideoUnderstandingRequest(
                    video_url="",  # 不传入视频
                    prompt=f"请分析以下视频片段内容：\n时间：{start_time:.1f}秒 - {end_time:.1f}秒\n语音内容：{text}\n分析要求：{self.prompt_template}",
                    max_tokens=8192,
                    temperature=0.7,
                    top_p=0.9
                )))
        except Exception as e:
            logger.error(f"大模型调用失败: {str(e)}", exc_info=True)
            raise

        # 解析大模型返回的JSON结果
        try:
            # 先清理响应内容，移除可能的markdown标记和多余文本
            content = response.content.strip()
            # 移除可能的```json和```包裹
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            # 寻找JSON边界
            start_idx = content.find("{")
            end_idx = content.rfind("}")
            if start_idx >= 0 and end_idx >= 0 and end_idx > start_idx:
                content = content[start_idx:end_idx+1]

            understanding_result = json.loads(content)

            # 确保输出格式包含必要的字段，与原处理器一致
            if prompt_manager.FIELD_SLICE_TEMPLATE not in understanding_result:
                # 如果返回格式不对，包装成正确的格式
                understanding_result = {
                    prompt_manager.FIELD_SLICE_TEMPLATE: understanding_result
                }

            return understanding_result

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败，原始内容: {response.content[:1000]}...", exc_info=True)
            raise ValueError(f"理解结果解析失败: {str(e)}")

    def _cleanup_temp_files(self, video_path: str, keyframes: List[Dict]):
        """清理临时文件"""
        try:
            # 清理下载的视频文件
            if os.path.exists(video_path):
                os.remove(video_path)

            # 清理关键帧对象存储（如果不需要长期保存）
            # 注意：这里暂时不删除，方便调试，生产环境可以开启
            # for kf in keyframes:
            #     if kf.get("object_name"):
            #         self.storage_client.delete_file(kf["object_name"])
        except Exception as e:
            logger.warning(f"清理临时文件失败: {str(e)}")
