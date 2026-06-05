"""视频库查询工具"""
from typing import Dict, Any
import json
import logging

from backend.store.database.async_database import get_db
from ..core.tool import BaseTool
from ..utils.tool_registry import register_tool
from backend.v1.app.admin.video_library.service.video_library_service import VideoLibraryService

logger = logging.getLogger(__name__)


@register_tool
class VideoLibraryQueryTool(BaseTool):
    """
    视频库查询工具，根据商品分类信息查询相关的视频素材
    """
    name: str = "query_video_library"
    description: str = "根据商品分类信息查询视频素材库中的相关视频，返回视频的标题、描述、URL、热度等信息"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "商品分类名称，例如：'手机', '电脑', '服装'等"
            },
            "category_id": {
                "type": "integer",
                "description": "商品分类ID，优先级高于category名称"
            },
            "min_hot_score": {
                "type": "integer",
                "description": "最低热度分数，返回热度大于等于该值的视频，默认80",
                "default": 80
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量，默认返回10条",
                "default": 10
            }
        },
        "required": []
    }

    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        执行视频库查询
        :param parameters: 查询参数，包含category或category_id等
        :return: JSON格式的查询结果字符串
        """
        import asyncio
        try:
            # 获取参数
            category = parameters.get("category")
            category_id = parameters.get("category_id")
            min_hot_score = parameters.get("min_hot_score", 80)
            limit = parameters.get("limit", 10)

            # 参数校验
            if not category and not category_id:
                return json.dumps({
                    "error": "参数错误",
                    "message": "必须提供category或category_id至少一个参数"
                }, ensure_ascii=False)

            # 运行异步查询
            async def query_videos():
                async for db in get_db():
                    # 查询视频列表
                    videos, total = await VideoLibraryService.get_video_list(
                        db=db,
                        page=1,
                        page_size=limit,
                        category=category,
                        category_id=category_id,
                        min_hot_score=min_hot_score
                    )

                    # 格式化结果
                    result = {
                        "total": total,
                        "count": len(videos),
                        "videos": []
                    }

                    for video in videos:
                        # 只返回需要的字段，避免返回过多信息
                        video_info = {
                            "video_id": video.get("id"),
                            "title": video.get("title"),
                            "description": video.get("description"),
                            "url": video.get("url"),
                            "cover_url": video.get("cover_url"),
                            "duration": video.get("duration"),
                            "hot_score": video.get("hot_score"),
                            "category": video.get("category"),
                            "tags": video.get("tags"),
                            "source_type": video.get("source_type"),
                            "created_at": video.get("created_at")
                        }
                        result["videos"].append(video_info)

                    return json.dumps(result, ensure_ascii=False, default=str)

                # 如果没有获取到数据库会话
                return json.dumps({
                    "error": "系统错误",
                    "message": "无法获取数据库连接"
                }, ensure_ascii=False)

            return asyncio.run(query_videos())

        except Exception as e:
            logger.error(f"查询视频库失败: {str(e)}", exc_info=True)
            return json.dumps({
                "error": "查询失败",
                "message": str(e)
            }, ensure_ascii=False)