"""产品知识库 DAO"""
import logging
from .base import CollectionDAO

logger = logging.getLogger(__name__)


class ProductKnowledgeDAO(CollectionDAO):
    """产品知识库集合数据访问层"""
    chroma_collection_name = "product_knowledge"
    milvus_collection_name = "product_knowledge"
    qdrant_collection_name = "product_knowledge"
