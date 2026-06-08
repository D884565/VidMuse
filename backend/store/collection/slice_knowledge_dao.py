from typing import List, Dict, Optional
from .base import CollectionDAO
from backend.v1.app.config.config import settings


class SliceKnowledgeDAO(CollectionDAO):
    """
    片段知识库集合数据访问层
    存储视频/音频切割后的片段知识向量
    """
    collection_name = settings.QDRANT_SLICE_COLLECTION

    def query_by_source_id(self, source_id: str, query_embeddings: List[List[float]],
                          n_results: int = 10, content_type: str = None) -> Dict:
        """
        查询指定来源的相关片段
        :param source_id: 来源ID（视频ID/音频ID）
        :param query_embeddings: 查询向量
        :param n_results: 返回结果数量
        :param content_type: 内容类型（可选：video, audio, text）
        :return: 查询结果
        """
        where = {"source_id": source_id}
        if content_type:
            where["content_type"] = content_type

        return self.query_similar(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where
        )

    def delete_by_source_id(self, source_id: str) -> None:
        """
        删除指定来源的所有片段
        :param source_id: 来源ID
        """
        self.delete_embeddings(where={"source_id": source_id})

    def add_slice_knowledge(self, slice_ids: List[str], source_id: str,
                           embeddings: List[List[float]], contents: List[str],
                           content_types: List[str], start_times: List[float] = None,
                           end_times: List[float] = None) -> None:
        """
        批量添加片段知识
        :param slice_ids: 片段ID列表
        :param source_id: 来源ID（视频ID/音频ID）
        :param embeddings: 向量列表
        :param contents: 片段内容列表
        :param content_types: 内容类型列表（video, audio, text）
        :param start_times: 开始时间列表（音视频可选）
        :param end_times: 结束时间列表（音视频可选）
        """
        if start_times is None:
            start_times = [0.0] * len(slice_ids)
        if end_times is None:
            end_times = [0.0] * len(slice_ids)

        metadatas = []
        for i in range(len(slice_ids)):
            metadata = {
                "source_id": source_id,
                "content_type": content_types[i],
                "start_time": start_times[i],
                "end_time": end_times[i],
                "duration": end_times[i] - start_times[i],
                "source": "slice_knowledge"
            }
            metadatas.append(metadata)

        self.add_embeddings(
            ids=slice_ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=contents
        )
