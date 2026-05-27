from typing import Dict, List, Any, Optional, Union
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
                 content_fields: List[Union[str, Dict[str, str]]] = None,
                 metadata_fields: List[str] = None,
                 id_field: str = "slice_id",
                 vector_db_type: str = VectorDBType.MILVUS,
                 vector_db_client=None):
        """
        初始化向量化处理器

        :param data_key: 从上下文中获取待向量化数据的键名
        :param content_fields: 需要生成向量的字段配置列表，支持两种格式：
            - 字符串格式：字段名，默认视为文本类型
            - 字典格式：{"name": "字段名", "type": "text/image_url/video_url"}
            默认使用["content"]
        :param metadata_fields: 需要作为元数据存储的字段名列表，默认存储所有字段
        :param id_field: 数据中唯一标识的字段名，用于向量ID
        :param vector_db_type: 向量数据库类型，默认使用Milvus
        :param vector_db_client: 向量数据库客户端，默认自动创建
        """
        self.data_key = data_key
        self.content_fields = self._parse_content_fields(content_fields or ["content"])
        self.metadata_fields = metadata_fields
        self.id_field = id_field

        # 初始化LLM客户端
        self.llm_client =VolcanoLLM(key=None, model_name=None)

        # 初始化向量数据库客户端
        self.vector_db_client = vector_db_client or get_vector_db_client(
            vector_db_type
        )

    def _parse_content_fields(self, fields: List[Union[str, Dict[str, str]]]) -> List[Dict[str, str]]:
        """
        解析内容字段配置，统一转换为字典格式

        :param fields: 内容字段配置列表
        :return: 标准化的字段配置列表
        """
        parsed_fields = []
        for field in fields:
            if isinstance(field, str):
                # 字符串格式，默认是文本类型
                parsed_fields.append({
                    "name": field,
                    "type": "text"
                })
            elif isinstance(field, dict) and "name" in field and "type" in field:
                # 字典格式，验证类型是否合法
                field_type = field["type"]
                if field_type not in ["text", "image_url", "video_url"]:
                    raise ValueError(f"Unsupported content field type: {field_type}")
                parsed_fields.append(field)
            else:
                raise ValueError(f"Invalid content field format: {field}")
        return parsed_fields

    def _prepare_multimodal_content(self, data: Dict) -> List[MultimodalContent]:
        """
        准备待向量化的多模态内容

        :param data: 数据对象
        :return: 多模态内容列表
        """
        contents = []
        for field_config in self.content_fields:
            field_name = field_config["name"]
            field_type = field_config["type"]
            value = data.get(field_name)

            if not value:
                continue

            if field_type == "text":
                # 文本内容
                contents.append(TextContent(text=str(value)))
            elif field_type == "image_url":
                # 图片URL内容
                contents.append(ImageUrlContent(image_url={"url": str(value)}))
            elif field_type == "video_url":
                # 视频URL内容
                contents.append(VideoUrlContent(video_url={"url": str(value)}))

        return contents

    def _prepare_metadata(self, data: Dict) -> Dict:
        """
        准备元数据，只保留配置的字段

        :param data: 数据对象
        :return: 元数据字典
        """
        if self.metadata_fields is None:
            # 默认存储所有字段
            return data.copy()

        metadata = {}
        for field in self.metadata_fields:
            if field in data:
                metadata[field] = data[field]
        return metadata

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行向量化逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含向量化结果
        """
        data_list = context.get(self.data_key, [])


        # 如果是单个对象而不是列表，包装成列表
        if isinstance(data_list, dict):
            data_list = [data_list]

        if not data_list:
            raise ValueError(f"No data found in context for key: {self.data_key}")

        # 准备所有需要向量化的内容
        ids = []
        all_contents = []  # 存储所有条目对应的多模态内容列表
        meta_data = []
        documents = []


        for data in data_list:
            # 获取ID
            item_id = str(data.get(self.id_field))
            if not item_id:
                raise ValueError(f"Missing id field '{self.id_field}' in data")

            # 准备多模态内容
            multimodal_contents = self._prepare_multimodal_content(data)
            if not multimodal_contents:
                # 没有内容的跳过
                continue

            # 准备元数据
            metadata = self._prepare_metadata(data)

            # 准备文档内容（将所有文本内容拼接，用于存储和检索）
            document_parts = []
            for content in multimodal_contents:
                if isinstance(content, TextContent):
                    document_parts.append(content.text)
                elif isinstance(content, ImageUrlContent):
                    document_parts.append(f"[IMAGE: {content.image_url['url']}]")
                elif isinstance(content, VideoUrlContent):
                    document_parts.append(f"[VIDEO: {content.video_url['url']}]")
            document = "\n".join(document_parts)

            ids.append(item_id)
            all_contents.append(multimodal_contents)
            meta_data.append(metadata)
            documents.append(document)

        if not all_contents:
            # 没有有效的内容需要向量化
            context.set(f"{self.data_key}_vectorized_count", 0)
            context.set(f"{self.data_key}_vectorized_ids", [])
            return context

        # 平铺所有多模态内容，生成对应的ID、元数据和文档
        flat_contents = []
        flat_ids = []
        flat_metadatas = []
        flat_documents = []

        for item_idx, (item_id, contents, metadata, document) in enumerate(zip(ids, all_contents, meta_data, documents)):
            for content_idx, content in enumerate(contents):
                # 为每个内容生成唯一ID
                if len(contents) == 1:
                    # 单个内容，使用原ID
                    content_id = item_id
                else:
                    # 多个内容，添加索引后缀
                    content_id = f"{item_id}_{content_idx}"

                # 复制元数据，添加内容索引信息
                content_metadata = metadata.copy()
                content_metadata["_item_id"] = item_id
                content_metadata["_content_index"] = content_idx

                flat_contents.append(content)
                flat_ids.append(content_id)
                flat_metadatas.append(content_metadata)
                flat_documents.append(document)

        # 批量生成向量
        embedding_request = EmbeddingRequest(texts=flat_contents)
        embedding_response = self.llm_client.embedding(embedding_request)
        embeddings = embedding_response.embeddings

        # 存储到向量数据库
        self.vector_db_client.add_embeddings(
            ids=flat_ids,
            embeddings=embeddings,
            metadatas=flat_metadatas,
            documents=flat_documents
        )

        # 记录结果到上下文
        context.set(f"{self.data_key}_vectorized_count", len(ids))
        context.set(f"{self.data_key}_vectorized_content_count", len(flat_ids))
        context.set(f"{self.data_key}_vectorized_ids", ids)
        context.set(f"{self.data_key}_embedding_usage", {
            "prompt_tokens": embedding_response.usage.prompt_tokens,
            "total_tokens": embedding_response.usage.total_tokens,
            "model": embedding_response.model
        })

        return context

    @classmethod
    def for_slice(cls, **kwargs) -> "VectorizationProcessor":
        """
        创建切片数据向量化处理器
        默认处理文本字段：content, template_name, template_type, summary
        如需处理图片/视频，可通过content_fields参数自定义：
        content_fields=[
            "content",  # 文本字段
            {"name": "frame_url", "type": "image_url"},  # 图片字段
            {"name": "video_url", "type": "video_url"}   # 视频字段
        ]
        """
        # 设置默认值，允许用户覆盖
        kwargs.setdefault("data_key", "valid_slices")
        kwargs.setdefault("content_fields", ["content", "template_name", "template_type", "summary"])
        kwargs.setdefault("id_field", "slice_id")
        return cls(**kwargs)

    @classmethod
    def for_video(cls, **kwargs) -> "VectorizationProcessor":
        """
        创建视频数据向量化处理器
        默认处理文本字段：title, description, tags, summary
        如需处理封面图/视频，可通过content_fields参数自定义
        """
        # 设置默认值，允许用户覆盖
        kwargs.setdefault("data_key", "valid_videos")
        kwargs.setdefault("content_fields", ["title", "description", "tags", "summary"])
        kwargs.setdefault("id_field", "video_id")
        return cls(**kwargs)

    @classmethod
    def for_product(cls, **kwargs) -> "VectorizationProcessor":
        """
        创建商品数据向量化处理器
        默认处理文本字段：name, description, category, features
        如需处理商品图片，可通过content_fields参数自定义
        """
        # 设置默认值，允许用户覆盖
        kwargs.setdefault("data_key", "valid_products")
        kwargs.setdefault("content_fields", ["name", "description", "category", "features"])
        kwargs.setdefault("id_field", "product_id")
        return cls(**kwargs)