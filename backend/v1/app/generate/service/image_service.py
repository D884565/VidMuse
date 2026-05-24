"""图片处理服务（混合方案：优先向量检索，无结果时使用占位图）"""
import os
import uuid
import tempfile
import logging
from typing import Optional

from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)


class ImageService:
    """场景配图处理服务（混合方案）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.storage = get_storage_client()

    def prepare_scene_images(self, script_content: dict) -> list[str]:
        """
        为剧本每个场景准备配图。

        策略：优先从素材库检索，无结果时使用占位图

        :param script_content: 剧本 JSON
        :returns: 各场景图片的本地路径列表
        """
        images = []
        for scene in script_content.get("body", []):
            keyword = scene.get("image_keyword", "default")
            image_path = self._get_image_for_scene(keyword)
            images.append(image_path)
        return images

    def _get_image_for_scene(self, keyword: str) -> str:
        """
        为单个场景获取图片。

        :param keyword: 场景关键词
        :returns: 图片本地路径
        """
        # 1. 尝试从素材库检索
        try:
            retrieved_image = self._retrieve_from_vector_db(keyword)
            if retrieved_image:
                logger.info(f"[图片服务] 从素材库检索到图片: {keyword}")
                return retrieved_image
        except Exception as e:
            logger.warning(f"[图片服务] 向量检索失败: {str(e)}")

        # 2. 检索失败，使用占位图
        logger.info(f"[图片服务] 使用占位图: {keyword}")
        return self._create_placeholder_image(keyword)

    def _retrieve_from_vector_db(self, keyword: str) -> Optional[str]:
        """
        从向量数据库检索相关内容。

        TODO: 实现向量检索逻辑，当前返回 None 直接走占位图

        :param keyword: 搜索关键词
        :returns: 图片本地路径，未找到返回 None
        """
        # 暂时跳过向量检索，直接使用占位图
        logger.info(f"[图片服务] 向量检索暂未实现，keyword={keyword}")
        return None

    def _create_placeholder_image(self, keyword: str) -> str:
        """创建占位图片"""
        output_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
        self._generate_placeholder_png(output_path, keyword)
        return output_path

    def _generate_placeholder_png(self, path: str, keyword: str):
        """生成一个简单的占位 PNG"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (1280, 720), (30, 30, 30))
            draw = ImageDraw.Draw(img)

            # 尝试使用系统字体
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except:
                font = ImageFont.load_default()

            # 绘制关键词文本
            draw.text((640, 360), keyword, fill=(255, 255, 255), font=font, anchor="mm")
            img.save(path, "PNG")
        except ImportError:
            # 没有 PIL 时创建一个空文件
            with open(path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)


image_service = ImageService()
