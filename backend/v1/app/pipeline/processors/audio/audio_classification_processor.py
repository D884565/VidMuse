import json
import requests
from typing import Dict, Any
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.config.config import settings
import logging

logger = logging.getLogger(__name__)

class AudioClassificationProcessor(BaseProcessor):
    """
    音频分类处理器
    调用火山引擎API实现音效分类、背景音乐识别等
    """

    def __init__(self):
        self.access_key = settings.VOLC_ENGINE_ACCESS_KEY
        self.secret_key = settings.VOLC_ENGINE_SECRET_KEY
        self.classification_endpoint = settings.VOLC_ENGINE_AUDIO_CLASSIFICATION_ENDPOINT

        if not self.access_key or not self.secret_key:
            logger.warning("火山引擎访问密钥未配置，音频分类功能将不可用")

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self.access_key or not self.secret_key:
            # 配置缺失时返回模拟数据，不阻断流程
            context.data["audio_type"] = "未知"
            context.data["has_background_music"] = False
            context.data["background_music_genre"] = "未知"
            context.data["objects"] = ["音频"]
            return context

        audio_url = context.data.get("audio_url")
        object_name = context.data.get("object_name")

        if not audio_url and not object_name:
            raise ValueError("audio_url or object_name is required")

        try:
            # 调用火山引擎音频分类API
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._generate_signature()}"
            }

            payload = {
                "appid": "your_app_id",
                "tasks": ["audio_type", "music_detection", "sound_effect_detection"],
                "audio": {
                    "url": audio_url if audio_url else self._get_presigned_url(object_name)
                }
            }

            response = requests.post(
                self.classification_endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

            if result.get("code") != 0:
                raise Exception(f"音频分类API调用失败: {result.get('message', '未知错误')}")

            # 解析返回结果
            classification_result = result.get("result", {})

            # 音频类型
            audio_type = classification_result.get("audio_type", "未知")
            context.data["audio_type"] = audio_type

            # 背景音乐检测
            music_result = classification_result.get("music_detection", {})
            context.data["has_background_music"] = music_result.get("has_music", False)
            context.data["background_music_genre"] = music_result.get("genre", "未知")

            # 音效检测
            sound_effects = classification_result.get("sound_effects", [])

            # 构建objects标签
            objects = []
            if audio_type:
                objects.append(audio_type)
            if context.data["has_background_music"]:
                objects.append("背景音乐")
            objects.extend(sound_effects)
            if not objects:
                objects = ["音频"]
            context.data["objects"] = list(set(objects))  # 去重

            logger.info(f"音频分类完成: 类型={audio_type}, 包含音效={len(sound_effects)}种")
            return context

        except Exception as e:
            logger.error(f"音频分类失败: {str(e)}", exc_info=True)
            # 分类失败时返回默认值，不阻断整个流程
            context.data["audio_type"] = "未知"
            context.data["has_background_music"] = False
            context.data["background_music_genre"] = "未知"
            context.data["objects"] = ["音频"]
            return context

    def _generate_signature(self) -> str:
        """生成火山引擎API签名"""
        return f"{self.access_key}:{self.secret_key}"

    def _get_presigned_url(self, object_name: str) -> str:
        """获取对象存储的临时访问URL"""
        from backend.store import get_storage_client
        client = get_storage_client()
        return client.get_presigned_url(object_name, expires_in=3600)
