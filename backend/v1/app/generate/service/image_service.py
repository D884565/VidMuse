"""图片处理服务（混合方案：优先向量检索，无结果时使用占位图）"""
import os
import uuid
import tempfile
import logging
from typing import Optional

from backend.providers import VolcanoLLM, EmbeddingRequest
from backend.store.vector.chromadb_client import get_chromadb_client
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)


class ImageService:
    """场景配图处理服务（混合方案）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.llm = VolcanoLLM(key=None, model_name=None)
        self.chromadb = get_chromadb_client()
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
        从向量数据库检索相关图片。

        :param keyword: 搜索关键词
        :returns: 图片本地路径，未找到返回 None
        """
        # 将关键词转换为向量
        embedding_request = EmbeddingRequest(texts=[keyword])
        embedding_response = self.llm._embedding(embedding_request)

        if not embedding_response.embeddings:
            return None

        query_embedding = embedding_response.embeddings[0]

        # 从 ChromaDB 检索相似向量
        results = self.chromadb.query_similar(
            query_embeddings=[query_embedding],
            n_results=1,
            where={"type": "image"}  # 只检索图片类型的素材
        )

        # 检查是否有结果
        if not results or not results.get("ids") or not results["ids"][0]:
            return None

        # 获取检索到的图片元数据
        metadata = results["metadatas"][0][0] if results.get("metadatas") else None
        if not metadata or "url" not in metadata:
            return None

        # 下载图片到本地
        image_url = metadata["url"]
        local_path = self._download_image(image_url)
        return local_path

    def _download_image(self, object_name: str) -> Optional[str]:
        """
        从对象存储下载图片到本地。

        :param object_name: 对象名称
        :returns: 本地文件路径
        """
        try:
            local_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
            self.storage.download_file(object_name, local_path)
            return local_path
        except Exception as e:
            logger.warning(f"[图片服务] 下载图片失败: {str(e)}")
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
