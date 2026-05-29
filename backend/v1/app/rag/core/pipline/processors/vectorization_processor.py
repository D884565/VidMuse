from typing import Dict, List, Any, Optional, Union
import json

from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import (
    EmbeddingRequest,
    TextContent,
    ImageUrlContent,
    VideoUrlContent,
    MultimodalContent
)
from backend.store.collection import (
    SliceKnowledgeDAO,
    VideoKnowledgeDAO,
    ImageKnowledgeDAO,
    ProductKnowledgeDAO,
    AudioKnowledgeDAO
)


class VectorizationProcessor(BaseProcessor):
    """
    向量化处理器
    将文本和图像数据转换为向量并存储到对应的知识库集合，支持多种类型数据的向量化
    """

    # 支持的存储类型与对应DAO的映射
    STORE_TYPE_MAPPING = {
        "slice": SliceKnowledgeDAO,
        "video": VideoKnowledgeDAO,
        "image": ImageKnowledgeDAO,
        "product": ProductKnowledgeDAO,
        "audio": AudioKnowledgeDAO
    }

    def __init__(self,
                 data_key: str = "valid_slices",
                 image_key: Optional[str] = "image_url",
                 store_type: str = "slice",
                 meta: Optional[Dict[str, Any]] = None,
                 embedding_model: Optional[str] = None,
                 id_key: str = "slice_id"):
        """
        初始化向量化处理器
        支持文本和图像的批量向量化，元数据会自动合并处理器配置和上下文中的元数据
        自动根据store_type选择对应的知识库集合进行存储

        职责说明：
        - 静态配置（初始化传入）：处理器的固定配置，每个实例独立
          - data_key: 从上下文中获取待向量化文本数据的键名，默认"valid_slices"
          - image_key: 从上下文中获取待向量化图像数据的键名，默认"image_url"，设为None则不处理图像
          - store_type: 存储类型，可选值：slice(视频分片), video(视频整体), image(图片), product(商品), audio(音频)，默认"slice"
          - meta: 全局默认元数据，会应用到所有向量化的内容上
          - embedding_model: 嵌入模型名称，不指定则使用默认模型
          - id_key: 数据中唯一标识字段的键名，用于生成向量ID，默认"slice_id"
        - 动态数据（从上下文获取）：流水线处理过程中传递的业务数据
          - 待向量化文本：context.get(data_key)，支持str、List[str]、或结构化TextContent dict
          - 待向量化图像：context.get(image_key)，支持str（URL）、List[str]、或结构化ImageUrlContent dict
          - 上下文元数据：context.get("meta_data")，会和初始化传入的meta合并，优先级更高
          - 来源ID：根据store_type不同，需要不同的来源ID：
            * slice/audio: 需要source_id（视频/音频ID）
            * video: 需要video_id
            * image: 需要image_set_id
            * product: 需要product_id
        - 输出数据（写入上下文）：
          - vectorization_result: 向量化结果，包含count、ids、documents、metadatas字段

        :param data_key: 从上下文中获取待向量化文本数据的键名
        :param image_key: 从上下文中获取待向量化图像数据的键名，设为None则不处理图像
        :param store_type: 存储类型，指定要存入哪个知识库集合
        :param meta: 全局默认元数据，会应用到所有向量化的内容上
        :param embedding_model: 嵌入模型名称，不指定则使用默认模型
        :param id_key: 数据中唯一标识字段的键名，用于生成向量ID
        """
        # 上下文键配置
        self.data_key = data_key
        self.image_key = image_key
        self.id_key = id_key

        # 存储配置
        if store_type not in self.STORE_TYPE_MAPPING:
            raise ValueError(f"不支持的存储类型: {store_type}，支持的类型: {list(self.STORE_TYPE_MAPPING.keys())}")
        self.store_type = store_type
        self.dao_class = self.STORE_TYPE_MAPPING[store_type]
        self.dao = self.dao_class()  # 初始化对应的DAO实例

        # 模型配置
        self.embedding_model = embedding_model
        # 初始化LLM客户端
        self.llm_client = VolcanoLLM(key=None, model_name=None)

        # 元数据配置
        self.meta = meta or {}


    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行向量化逻辑
        支持文本和图像的批量向量化，自动根据store_type存储到对应的知识库集合

        :param context: 流水线上下文
        :return: 修改后的上下文，包含向量化结果
        """
        # 1. 从上下文获取公共元数据和必要的来源ID
        context_meta = context.get("meta_data", {})
        if isinstance(context_meta, dict):
            base_meta = {**self.meta, **context_meta}
        else:
            base_meta = self.meta.copy()

        # 根据存储类型获取必要的来源ID
        source_id = None
        if self.store_type == "slice":
            source_id = context.get("video_id") or context.get("source_id")
            if not source_id:
                raise ValueError("存储类型为slice时，上下文必须包含video_id或source_id")
        elif self.store_type == "video":
            source_id = context.get("video_id")
            if not source_id:
                raise ValueError("存储类型为video时，上下文必须包含video_id")
        elif self.store_type == "image":
            source_id = context.get("image_set_id") or context.get("video_id")
            if not source_id:
                raise ValueError("存储类型为image时，上下文必须包含image_set_id或video_id")
        elif self.store_type == "product":
            source_id = context.get("product_id")
            if not source_id:
                raise ValueError("存储类型为product时，上下文必须包含product_id")
        elif self.store_type == "audio":
            source_id = context.get("source_id") or context.get("video_id")
            if not source_id:
                raise ValueError("存储类型为audio时，上下文必须包含source_id或video_id")

        # 2. 处理文本向量化和存储
        text_result = self._process_text_data(context, source_id, base_meta)

        # 3. 处理图像向量化和存储（如果配置了image_key）
        image_result = self._process_image_data(context, source_id, base_meta) if self.image_key else None

        # 4. 汇总结果存入上下文
        total_count = text_result["count"] + (image_result["count"] if image_result else 0)
        result = {
            "count": total_count,
            "text_count": text_result["count"],
            "image_count": image_result["count"] if image_result else 0,
            "text_ids": text_result["ids"],
            "image_ids": image_result["ids"] if image_result else [],
            "store_type": self.store_type,
            "source_id": source_id
        }
        context.set("vectorization_result", result)

        return context

    def _process_text_data(self, context: PipelineContext, source_id: str, base_meta: Dict) -> Dict:
        """处理文本数据的向量化和存储"""
        text_data = context.get(self.data_key, [])

        # 统一转换为列表格式
        if isinstance(text_data, (str, dict)):
            text_data = [text_data]
        if not text_data:
            return {"count": 0, "ids": []}

        # 准备文本内容
        texts = []
        contents = []
        ids = []
        for i, data in enumerate(text_data):
            if isinstance(data, str):
                # 纯文本
                texts.append(TextContent(text=data))
                contents.append(data)
                # 生成ID：如果有id_key则使用，否则用索引
                ids.append(f"{source_id}_text_{i}")
            elif isinstance(data, dict):
                # 字典类型，优先取id_key作为ID，内容取文本字段
                text_content = data.get("content") or data.get("text") or str(data)
                texts.append(TextContent(text=text_content))
                contents.append(text_content)
                ids.append(data.get(self.id_key, f"{source_id}_text_{i}"))
            else:
                context.add_error(ValueError(f"Unsupported text data format: {type(data)}"))
                continue

        if not texts:
            return {"count": 0, "ids": []}

        # 调用嵌入接口
        response = self.llm_client.embedding(EmbeddingRequest(
            texts=texts,
            model=self.embedding_model
        ))
        embeddings = response.embeddings

        if len(embeddings) != len(texts):
            raise ValueError(f"Text embedding count mismatch: expected {len(texts)}, got {len(embeddings)}")

        # 根据存储类型调用对应DAO的add方法
        if self.store_type == "slice":
            # 分片知识：content_type为text
            content_types = ["text"] * len(ids)
            # 尝试从数据中获取时间信息
            start_times = []
            end_times = []
            for data in text_data:
                if isinstance(data, dict):
                    start_times.append(data.get("start_time", 0.0))
                    end_times.append(data.get("end_time", 0.0))
                else:
                    start_times.append(0.0)
                    end_times.append(0.0)

            self.dao.add_slice_knowledge(
                slice_ids=ids,
                source_id=source_id,
                embeddings=embeddings,
                contents=contents,
                content_types=content_types,
                start_times=start_times,
                end_times=end_times
            )

        elif self.store_type == "video":
            # 视频知识
            titles = []
            categories = []
            tags = []
            for data in text_data:
                if isinstance(data, dict):
                    titles.append(data.get("title", ""))
                    categories.append(data.get("category", "general"))
                    tags.append(data.get("tags", []))
                else:
                    titles.append("")
                    categories.append("general")
                    tags.append([])

            self.dao.add_video_knowledge(
                knowledge_ids=ids,
                video_id=source_id,
                embeddings=embeddings,
                contents=contents,
                titles=titles,
                categories=categories,
                tags=tags
            )

        elif self.store_type == "product":
            # 产品知识
            knowledge_types = []
            for data in text_data:
                if isinstance(data, dict):
                    knowledge_types.append(data.get("type", "general"))
                else:
                    knowledge_types.append("general")

            self.dao.add_product_knowledge(
                knowledge_ids=ids,
                product_id=source_id,
                embeddings=embeddings,
                contents=contents,
                knowledge_types=knowledge_types
            )

        elif self.store_type == "audio":
            # 音频知识
            durations = []
            languages = []
            for data in text_data:
                if isinstance(data, dict):
                    durations.append(data.get("duration", 0.0))
                    languages.append(data.get("language", "zh"))
                else:
                    durations.append(0.0)
                    languages.append("zh")

            self.dao.add_audio_knowledge(
                audio_ids=ids,
                source_id=source_id,
                embeddings=embeddings,
                transcripts=contents,
                durations=durations,
                languages=languages
            )

        return {"count": len(embeddings), "ids": ids}

    def _process_image_data(self, context: PipelineContext, source_id: str, base_meta: Dict) -> Dict:
        """处理图像数据的向量化和存储"""
        image_data = context.get(self.image_key, [])

        # 统一转换为列表格式
        if isinstance(image_data, (str, dict)):
            image_data = [image_data]
        if not image_data:
            return {"count": 0, "ids": []}

        # 准备图像内容
        images = []
        descriptions = []
        image_urls = []
        ids = []
        for i, data in enumerate(image_data):
            if isinstance(data, str):
                # 纯URL
                images.append(ImageUrlContent(image_url={"url": data}))
                descriptions.append(f"图片_{i}")
                image_urls.append(data)
                ids.append(f"{source_id}_img_{i}")
            elif isinstance(data, dict) and "image_url" in data:
                # 结构化图像内容
                images.append(ImageUrlContent(**data))
                description = data.get("description") or data.get("alt") or f"图片_{i}"
                descriptions.append(description)
                image_urls.append(data["image_url"]["url"])
                ids.append(data.get(self.id_key, f"{source_id}_img_{i}"))
            elif isinstance(data, dict) and "url" in data:
                # 简化的URL格式
                url = data["url"]
                images.append(ImageUrlContent(image_url={"url": url}))
                description = data.get("description") or data.get("alt") or f"图片_{i}"
                descriptions.append(description)
                image_urls.append(url)
                ids.append(data.get(self.id_key, f"{source_id}_img_{i}"))
            else:
                context.add_error(ValueError(f"Unsupported image data format: {type(data)}"))
                continue

        if not images:
            return {"count": 0, "ids": []}

        # 调用嵌入接口
        response = self.llm_client.embedding(EmbeddingRequest(
            texts=images,
            model=self.embedding_model
        ))
        embeddings = response.embeddings

        if len(embeddings) != len(images):
            raise ValueError(f"Image embedding count mismatch: expected {len(images)}, got {len(embeddings)}")

        # 图像统一存入ImageKnowledgeDAO
        image_dao = ImageKnowledgeDAO()
        image_dao.add_image_knowledge(
            image_ids=ids,
            image_set_id=source_id,
            embeddings=embeddings,
            descriptions=descriptions,
            image_urls=image_urls
        )

        return {"count": len(embeddings), "ids": ids}

