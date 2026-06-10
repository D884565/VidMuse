from typing import Dict, Any, List, Optional
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.store.collection.video_knowledge_dao import VideoKnowledgeDAO
from backend.store.collection.slice_knowledge_dao import SliceKnowledgeDAO
import logging

logger = logging.getLogger(__name__)


class VectorFetchProcessor(BaseProcessor):
    """
    向量数据拉取处理器
    直接从向量库拉取指定集合的向量和元数据，无需依赖报告表
    """

    def __init__(self,
                 collection_type: str = "both",  # slice / video / both
                 max_vectors: int = 800,
                 batch_size: int = 100):
        """
        初始化处理器

        :param collection_type: 拉取的集合类型：slice(仅片段)、video(仅视频)、both(两者都拉取)
        :param max_vectors: 最大拉取向量数量
        :param batch_size: 批量拉取大小
        """
        self.collection_type = collection_type
        self.max_vectors = max_vectors
        self.batch_size = batch_size
        self.video_dao = None
        self.slice_dao = None

    def _init_daos(self):
        """延迟初始化DAO，只在实际处理时才连接数据库"""
        if self.video_dao is None:
            self.video_dao = VideoKnowledgeDAO()
        if self.slice_dao is None:
            self.slice_dao = SliceKnowledgeDAO()

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 根据配置拉取slice集合数据
        2. 根据配置拉取video集合数据
        3. 将原始数据存入上下文
        """
        logger.info(f"开始从向量库拉取数据，类型: {self.collection_type}, 最大数量: {self.max_vectors}")

        # 初始化DAO
        self._init_daos()

        slice_data = []
        video_data = []

        # 拉取片段集合
        if self.collection_type in ["slice", "both"]:
            logger.info("开始拉取slice_collection数据...")
            slice_data = self._fetch_collection_data("slice")
            logger.info(f"成功拉取slice数据: {len(slice_data)} 条")

        # 拉取视频集合
        if self.collection_type in ["video", "both"]:
            logger.info("开始拉取video_collection数据...")
            video_data = self._fetch_collection_data("video")
            logger.info(f"成功拉取video数据: {len(video_data)} 条")

        # 存入上下文
        context.set("SLICE_COLLECTION_DATA", slice_data)
        context.set("VIDEO_COLLECTION_DATA", video_data)

        logger.info(f"向量拉取完成: slice={len(slice_data)}, video={len(video_data)}")

        return context

    def _fetch_collection_data(self, collection_name: str) -> List[Dict[str, Any]]:
        """拉取指定集合的所有数据"""
        dao = self.slice_dao if collection_name == "slice" else self.video_dao
        all_data = []
        offset = 0

        while len(all_data) < self.max_vectors:
            try:
                from qdrant_client import models
                results, next_offset = dao._vector_client.client.scroll(
                    collection_name=dao.collection_name,
                    limit=self.batch_size,
                    offset=offset,
                    with_vectors=True,
                    with_payload=True
                )

                if not results:
                    break

                for point in results:
                    if point.vector and point.payload:
                        metadata = point.payload.get("metadata", {})
                        data_item = {
                            "point_id": point.id,
                            "vector": point.vector,
                            "document": point.payload.get("document", ""),
                            "metadata": metadata,
                            "original_id": point.payload.get("original_id", "")
                        }
                        all_data.append(data_item)

                offset = next_offset
                if next_offset is None:
                    break

            except Exception as e:
                logger.error(f"拉取 {collection_name} 失败: {str(e)}", exc_info=True)
                break

        return all_data
