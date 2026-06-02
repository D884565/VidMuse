import json
import requests
from typing import Dict, Any
import logging
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.config.config import settings

logger = logging.getLogger(__name__)

class AudioASRProcessor(BaseProcessor):
    """
    语音识别处理器
    调用火山引擎API实现语音转文字、说话人识别、语种识别
    """

    def __init__(self):
        self.access_key = settings.VOLC_ENGINE_ACCESS_KEY
        self.secret_key = settings.VOLC_ENGINE_SECRET_KEY
        self.asr_endpoint = settings.VOLC_ENGINE_ASR_ENDPOINT
        self.app_id = settings.VOLC_ENGINE_ASR_APP_ID

        if not self.access_key or not self.secret_key:
            logger.warning("火山引擎访问密钥未配置，ASR功能将使用模拟数据")

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self.access_key or not self.secret_key:
            # 配置缺失时返回模拟数据，不阻断流程
            context.data["transcript"] = "语音识别功能未配置，使用模拟识别结果"
            context.data["language"] = "zh-CN"
            context.data["speakers"] = ["说话人1"]
            return context

        audio_url = context.data.get("audio_url")
        object_name = context.data.get("object_name")

        if not audio_url and not object_name:
            logger.warning("上下文中未找到audio_url或object_name，返回默认值")
            context.data["transcript"] = "未找到音频文件"
            context.data["language"] = "unknown"
            context.data["speakers"] = []
            return context

        try:
            # 调用火山引擎ASR API
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._generate_signature()}"
            }

            final_audio_url = audio_url if audio_url else self._get_presigned_url(object_name)

            payload = {
                "appid": self.app_id,
                "speaker_diarization": True,  # 开启说话人识别
                "language": "zh-CN,en-US",  # 支持中英双语
                "audio": {
                    "url": final_audio_url
                }
            }

            response = requests.post(
                self.asr_endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

            if result.get("code") != 0:
                raise Exception(f"ASR API调用失败: {result.get('message', '未知错误')}")

            # 解析返回结果
            asr_result = result.get("result", {})
            context.data["transcript"] = asr_result.get("text", "")
            context.data["language"] = asr_result.get("language", "zh-CN")

            # 处理说话人识别结果
            speakers = []
            if "speaker_info" in asr_result:
                speaker_ids = {seg.get("speaker_id") for seg in asr_result["speaker_info"]}
                speakers = [f"说话人{id}" for id in sorted(speaker_ids)]
            context.data["speakers"] = speakers if speakers else ["说话人1"]

            logger.info(f"语音识别完成，识别到 {len(speakers)} 个说话人，文本长度: {len(context.data['transcript'])}")
            return context

        except Exception as e:
            logger.error(f"语音识别失败: {str(e)}", exc_info=True)
            # 识别失败时返回默认值，不阻断整个流程
            context.data["transcript"] = "语音识别失败"
            context.data["language"] = "unknown"
            context.data["speakers"] = []
            return context

    def _generate_signature(self) -> str:
        """生成火山引擎API签名"""
        # 实际项目中需要实现完整的签名逻辑，这里简化处理
        # 参考火山引擎文档: https://www.volcengine.com/docs/6561/107784
        return f"{self.access_key}:{self.secret_key}"

    def _get_presigned_url(self, object_name: str) -> str:
        """获取对象存储的临时访问URL"""
        from backend.store import get_storage_client
        client = get_storage_client()
        return client.get_presigned_url(object_name, expires_in=3600)
