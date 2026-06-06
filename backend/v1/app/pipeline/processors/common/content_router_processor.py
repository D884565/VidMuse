from typing import Dict, List, Any
from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
import logging

logger = logging.getLogger(__name__)


class ContentRouterProcessor(BaseProcessor):
    """
    内容路由处理器
    根据输入的内容类型（图片/文本/视频）自动路由到对应的处理流程
    支持单类型和多类型组合输入
    """

    # 内容类型常量
    CONTENT_TYPE_TEXT = "text"
    CONTENT_TYPE_IMAGE = "image"
    CONTENT_TYPE_VIDEO = "video"

    def __init__(self):
        """
        初始化内容路由处理器
        """
        pass

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行内容路由逻辑
        输入（从上下文获取）：
        - images: List[str] 图片URL列表（可选）
        - description: str 商品描述文本（可选）
        - video_url: str 视频URL（可选）
        - video_object_name: str 视频对象存储路径（可选）

        输出（写入上下文）：
        - content_types: List[str] 检测到的内容类型列表
        - has_text: bool 是否包含文本内容
        - has_image: bool 是否包含图片内容
        - has_video: bool 是否包含视频内容

        :param context: 流水线上下文
        :return: 修改后的上下文
        """
        content_types = []
        has_text = False
        has_image = False
        has_video = False

        # 检测文本内容
        description = context.get("description", "")
        if description and isinstance(description, str) and description.strip():
            has_text = True
            content_types.append(self.CONTENT_TYPE_TEXT)
            logger.debug(f"检测到文本内容，长度: {len(description)}")

        # 检测图片内容
        images = context.get("images", [])
        if images and isinstance(images, list) and len(images) > 0:
            # 过滤掉空的图片URL
            valid_images = [img for img in images if img and isinstance(img, str) and img.strip()]
            if valid_images:
                has_image = True
                content_types.append(self.CONTENT_TYPE_IMAGE)
                context.set("images", valid_images)  # 更新为有效图片列表
                logger.debug(f"检测到图片内容，数量: {len(valid_images)}")

        # 检测视频内容
        video_url = context.get("video_url", "")
        video_object_name = context.get("video_object_name", "")
        if (video_url and isinstance(video_url, str) and video_url.strip()) or \
           (video_object_name and isinstance(video_object_name, str) and video_object_name.strip()):
            has_video = True
            content_types.append(self.CONTENT_TYPE_VIDEO)
            logger.debug(f"检测到视频内容")

        # 验证至少有一种内容类型
        if not content_types:
            raise ValueError("至少需要提供一种内容类型：文本(description)、图片(images)或视频(video_url/video_object_name)")

        # 存储检测结果到上下文
        context.set("content_types", content_types)
        context.set("has_text", has_text)
        context.set("has_image", has_image)
        context.set("has_video", has_video)

        logger.info(f"内容路由完成，检测到的内容类型: {content_types}")

        return context
