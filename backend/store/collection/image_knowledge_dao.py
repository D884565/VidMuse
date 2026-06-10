"""图片知识库 DAO"""
import logging
from .base import CollectionDAO

logger = logging.getLogger(__name__)


class ImageKnowledgeDAO(CollectionDAO):
    """图片知识库集合数据访问层"""
    collection_name = "img_knowledge"
