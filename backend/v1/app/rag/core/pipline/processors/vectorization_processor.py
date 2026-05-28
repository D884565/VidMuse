from typing import Dict, List, Any, Optional, Union

from jinja2 import meta
from openai.types import embedding

from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import (
    EmbeddingRequest,
    TextContent,
    ImageUrlContent,
    VideoUrlContent,
    MultimodalContent
)
from backend.store.vector import get_vector_db_client, VectorDBType


class VectorizationProcessor(BaseProcessor):
    """
    向量化处理器
    将文本数据转换为向量并存储到向量数据库，支持切片、视频、商品等多种类型数据的向量化
    """

    def __init__(self,
                 data_key: str = "valid_slices",
                 image_key: Optional[ str] = "image_url",
                 vector_db_type: str = VectorDBType.MILVUS,
                 meta: Optional[Dict[str, Any]] = None,
                 vector_db_client=None):
        """
        初始化向量化处理器
        目前仅支持文本和图片进行向量化
        :param data_key: 从上下文中获取待向量化数据的键名
        :param vector_db_type: 向量数据库类型，默认使用Milvus
        :param vector_db_client: 向量数据库客户端，默认自动创建
        """
        # 用于标记要取的key
        self.data_key = data_key
        self.image_key = image_key
        # 初始化LLM客户端
        self.llm_client =VolcanoLLM(key=None, model_name=None)

        self.meta = meta or {}
        # 初始化向量数据库客户端
        self.vector_db_client = vector_db_client or get_vector_db_client(
            vector_db_type
        )


    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行向量化逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含向量化结果
        """

        # 规定data_list存要向量化的数据
        data_list = context.get(self.data_key, [])

        # todo 后续修改milvus_client 目前仅支持文本向量
        if self.image_key:
            images_list = context.get(self.image_key, [])


        # 如果是单个对象而不是列表，包装成列表
        if isinstance(data_list, dict):
            data_list = [data_list]

        if not data_list:
            raise ValueError(f"No data found in context for key: {self.data_key}")

        # 文档内容从通道内部获取也是需要向量化的内容
        documents = []
        # 元数据可以从解析通道自动赋值也可以从外部传入
        meta_data = []
        if self.meta:
            meta_data.append(self.meta)

        con_meta = context.get("meta_data")
        if con_meta and len(con_meta) != 0:
            meta_data.append(con_meta)

        embeddings = []


        for data in data_list:
            if isinstance(data, str):
                documents.append(data)
                response = self.llm_client.embedding(EmbeddingRequest(texts=[
                    TextContent(text=data)
                ]))
                embeddings.append(response.embeddings[0])


        self.vector_db_client.add_embeddings(ids=[str(i) for i in range(len(documents))],embeddings=embeddings,metadatas=meta_data)

        return context

