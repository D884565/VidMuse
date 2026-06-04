from typing import List, Dict, Optional
from .base import CollectionDAO
from backend.v1.app.config.config import settings


class AudioKnowledgeDAO(CollectionDAO):
    """
    音频知识库集合数据访问层
    存储音频特征向量和相关知识
    """
    chroma_collection_name = settings.CHROMADB_AUDIO_COLLECTION
    milvus_collection_name = settings.MILVUS_AUDIO_COLLECTION
    qdrant_collection_name = settings.QDRANT_AUDIO_COLLECTION

    def query_by_audio_id(self, audio_id: str, query_embeddings: List[List[float]],
                         n_results: int = 10) -> Dict:
        """
        查询指定音频的相关内容
        :param audio_id: 音频ID
        :param query_embeddings: 查询向量
        :param n_results: 返回结果数量
        :return: 查询结果
        """
        return self.query_similar(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where={"audio_id": audio_id}
        )

    def delete_by_audio_id(self, audio_id: str) -> None:
        """
        删除指定音频的所有内容
        :param audio_id: 音频ID
        """
        self.delete_embeddings(where={"audio_id": audio_id})

    def add_audio_knowledge(self, audio_ids: List[str], source_id: str,
                           embeddings: List[List[float]], transcripts: List[str],
                           durations: List[float], languages: List[str] = None) -> None:
        """
        批量添加音频知识
        :param audio_ids: 音频ID列表
        :param source_id: 来源ID（所属视频/专辑ID）
        :param embeddings: 音频特征向量列表
        :param transcripts: 音频转录文本列表
        :param durations: 音频时长列表
        :param languages: 音频语言列表（可选）
        """
        if languages is None:
            languages = ["zh"] * len(audio_ids)

        metadatas = [
            {
                "source_id": source_id,
                "duration": duration,
                "language": language,
                "source": "audio_knowledge"
            }
            for duration, language in zip(durations, languages)
        ]

        self.add_embeddings(
            ids=audio_ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=transcripts
        )
