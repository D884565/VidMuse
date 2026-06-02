import os
import tempfile
import requests
from pydub import AudioSegment
from typing import Dict, Any
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.store import get_storage_client
from backend.v1.app.config.config import settings
import logging

logger = logging.getLogger(__name__)

class AudioInfoExtractProcessor(BaseProcessor):
    """
    音频基础信息提取处理器
    提取时长、采样率、声道数、比特率等基础属性
    """

    def process(self, context: PipelineContext) -> PipelineContext:
        audio_url = context.data.get("audio_url")
        object_name = context.data.get("object_name")

        if not audio_url and not object_name:
            error_msg = "audio_url or object_name is required in context data"
            logger.error(error_msg)
            context.add_error(ValueError(error_msg))
            return context

        try:
            # 下载音频文件到临时目录
            client = get_storage_client()
            with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp_file:
                if object_name:
                    # 从对象存储下载
                    content = client.download_fileobj(object_name)
                    tmp_file.write(content)
                else:
                    # 从URL下载
                    response = requests.get(audio_url, timeout=30)
                    response.raise_for_status()
                    tmp_file.write(response.content)
                tmp_path = tmp_file.name

            # 使用pydub读取音频信息
            audio = AudioSegment.from_file(tmp_path)

            # 提取基础信息
            context.data["duration"] = len(audio) / 1000.0  # 转换为秒
            context.data["sample_rate"] = audio.frame_rate
            context.data["channels"] = audio.channels
            context.data["bitrate"] = audio.frame_rate * audio.sample_width * 8 * audio.channels

            # 清理临时文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

            logger.info(f"音频基础信息提取完成: 时长={context.data['duration']}s, 采样率={context.data['sample_rate']}Hz, 声道数={context.data['channels']}, 比特率={context.data['bitrate']}bps")
            return context

        except Exception as e:
            error_msg = f"音频基础信息提取失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 清理临时文件
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            context.add_error(e)
            return context
