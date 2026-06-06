"""相似爆款视频检索工具"""
from typing import Dict, Any, List
import json
import logging
import asyncio

from ..core.tool import BaseTool
from ..utils.tool_registry import register_tool

# 可选导入SearchEngine相关依赖
try:
    from backend.v1.app.search import SearchEngine, SearchQuery
    from backend.v1.app.search.config import SearchConfig
    HAS_SEARCH_ENGINE = True
except ImportError:
    SearchEngine = None
    SearchQuery = None
    SearchConfig = None
    HAS_SEARCH_ENGINE = False

logger = logging.getLogger(__name__)


@register_tool
class SimilarVideoSearchTool(BaseTool):
    """
    相似爆款视频检索工具，根据输入的视频解析报告，从视频知识库中检索相似的爆款视频报告
    """
    name: str = "search_similar_hot_videos"
    description: str = "根据视频解析报告内容，检索知识库中相似的爆款视频分析报告，返回相似视频的创意、脚本、数据表现等信息"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "video_report": {
                "type": "string",
                "description": "待分析的视频解析报告文本内容，包含视频的主题、脚本、内容结构、受众分析、数据表现等信息"
            },
            "top_k": {
                "type": "integer",
                "description": "返回的相似视频数量，默认返回5条",
                "default": 5
            },
            "min_score": {
                "type": "number",
                "description": "最低相似度阈值，0-1之间，默认0.6",
                "default": 0.6
            }
        },
        "required": ["video_report"]
    }

    def __init__(self):
        super().__init__()
        self.search_engine = self._init_search_engine()

    def _init_search_engine(self) -> SearchEngine:
        """
        初始化检索引擎，仅配置向量数据库渠道，使用video_knowledge集合
        """
        if not HAS_SEARCH_ENGINE or not SearchConfig:
            logger.warning("SearchEngine不可用，相似视频检索功能将无法使用")
            return None

        try:
            # 自定义配置，仅启用向量数据库渠道，指定video_knowledge集合
            search_config = SearchConfig()
            search_config.ENABLED_CHANNELS = ["vector_db"]
            search_config.CHANNEL_CONFIG = {
                "vector_db": {
                    "enabled": True,
                    "collection": "video_knowledge",
                    "weight": 1.0,
                    "timeout": 10
                }
            }
            # 配置后处理器，过滤低分结果
            search_config.POST_PROCESSOR_CONFIG["result_filter"]["min_score"] = 0.6
            # 不需要其他查询处理器和后处理器
            search_config.ENABLED_QUERY_PROCESSORS = []
            search_config.ENABLED_POST_PROCESSORS = ["result_filter", "reranker"]

            # 创建检索引擎实例
            return SearchEngine(search_config)
        except Exception as e:
            logger.error(f"初始化相似视频检索引擎失败: {str(e)}", exc_info=True)
            return None

    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        执行相似爆款视频检索
        :param parameters: 检索参数，包含video_report等
        :return: JSON格式的检索结果字符串
        """
        if not self.search_engine:
            return json.dumps({
                "error": "功能不可用",
                "message": "检索引擎初始化失败，无法执行相似视频检索"
            }, ensure_ascii=False)

        try:
            # 获取参数
            video_report = parameters.get("video_report", "")
            top_k = parameters.get("top_k", 5)
            min_score = parameters.get("min_score", 0.6)

            # 参数校验
            if not video_report or len(video_report.strip()) < 10:
                return json.dumps({
                    "error": "参数错误",
                    "message": "视频解析报告内容不能为空或过短"
                }, ensure_ascii=False)

            # 动态调整最小得分阈值
            if min_score != 0.6:
                self.search_engine.config.POST_PROCESSOR_CONFIG["result_filter"]["min_score"] = min_score
                self.search_engine.registry.config["POST_PROCESSOR_CONFIG"]["result_filter"]["min_score"] = min_score

            # 构建检索查询
            search_query = SearchQuery(
                query_text=video_report,
                top_k=top_k,
                metadata={
                    "search_type": "similar_video",
                    "report_length": len(video_report)
                }
            )

            # 执行检索
            results = self.search_engine.search(search_query)

            # 格式化结果
            formatted_results = []
            for result in results:
                video_info = {
                    "result_id": result.result_id,
                    "similarity_score": round(result.score, 4),
                    "content": result.content,
                    "source_type": result.source_type,
                    "metadata": result.metadata
                }
                # 提取常用字段到外层，方便使用
                if result.metadata:
                    if "video_title" in result.metadata:
                        video_info["video_title"] = result.metadata["video_title"]
                    if "hot_score" in result.metadata:
                        video_info["hot_score"] = result.metadata["hot_score"]
                    if "play_count" in result.metadata:
                        video_info["play_count"] = result.metadata["play_count"]
                    if "like_count" in result.metadata:
                        video_info["like_count"] = result.metadata["like_count"]
                    if "comment_count" in result.metadata:
                        video_info["comment_count"] = result.metadata["comment_count"]
                    if "share_count" in result.metadata:
                        video_info["share_count"] = result.metadata["share_count"]
                    if "tags" in result.metadata:
                        video_info["tags"] = result.metadata["tags"]
                    if "category" in result.metadata:
                        video_info["category"] = result.metadata["category"]

                formatted_results.append(video_info)

            # 返回结果
            return json.dumps({
                "status": "success",
                "query_length": len(video_report),
                "total_results": len(formatted_results),
                "similar_videos": formatted_results
            }, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"相似视频检索失败: {str(e)}", exc_info=True)
            return json.dumps({
                "error": "检索失败",
                "message": str(e)
            }, ensure_ascii=False)
