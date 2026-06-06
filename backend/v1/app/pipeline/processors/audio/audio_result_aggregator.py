from typing import Dict, Any
import logging
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext

logger = logging.getLogger(__name__)

class AudioResultAggregator(BaseProcessor):
    """
    音频结果聚合处理器
    将所有处理器的结果整理为符合现有ai_features结构的格式
    """

    def process(self, context: PipelineContext) -> PipelineContext:
        try:
            # 基础信息
            duration = context.data.get("duration", 0)
            audio_type = context.data.get("audio_type", "音频")
            objects = context.data.get("objects", ["音频"])

            # 推断场景和情绪
            scene = self._infer_scene(audio_type, context.data)
            mood = self._infer_mood(context.data)

            # 构建ai_features
            ai_features = {
                "scene": scene,
                "mood": mood,
                "objects": objects,
                "duration": duration,
                "sample_rate": context.data.get("sample_rate"),
                "channels": context.data.get("channels"),
                "bitrate": context.data.get("bitrate"),
                "transcript": context.data.get("transcript", ""),
                "speakers": context.data.get("speakers", []),
                "language": context.data.get("language", "unknown"),
                "audio_type": audio_type,
                "has_background_music": context.data.get("has_background_music", False),
                "background_music_genre": context.data.get("background_music_genre", "未知")
            }

            # 构建最终结果结构，与视频解析保持一致
            result = {
                "slice_len": 1,  # 不需要切片，固定为1
                "scene": scene,
                "mood": mood,
                "objects": objects,
                "ai_features": ai_features
            }

            # 覆盖context.data为最终结果
            context.data = result

            logger.info(f"音频结果聚合完成，特征包含 {len(ai_features)} 个字段")
            return context

        except Exception as e:
            logger.error(f"音频结果聚合失败: {str(e)}", exc_info=True)
            raise

    def _infer_scene(self, audio_type: str, data: Dict[str, Any]) -> str:
        """根据音频类型和内容推断场景"""
        scene_map = {
            "访谈": "访谈音频",
            "音乐": "音乐音频",
            "演讲": "演讲音频",
            "播客": "播客音频",
            "有声书": "有声书",
            "电影剪辑": "影视音频",
            "自然音效": "自然音效",
            "新闻": "新闻音频"
        }
        return scene_map.get(audio_type, f"{audio_type}音频")

    def _infer_mood(self, data: Dict[str, Any]) -> str:
        """根据内容推断情绪"""
        # 简单实现，可根据ASR文本情感分析进一步优化
        if data.get("has_background_music", False):
            genre = data.get("background_music_genre", "")
            if genre in ["轻快", "活泼", "欢快"]:
                return "愉悦"
            elif genre in ["舒缓", "柔和", "安静"]:
                return "平静"
            elif genre in ["激昂", "振奋"]:
                return "激昂"
            elif genre in ["悲伤", "忧郁"]:
                return "悲伤"

        # 根据音频类型推断
        audio_type = data.get("audio_type", "")
        if audio_type == "访谈":
            return "正式"
        elif audio_type == "音乐":
            return "愉悦"
        elif audio_type == "演讲":
            return "激昂"

        return "未知"
