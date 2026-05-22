from sqlalchemy import Column, BigInteger, VARCHAR, JSON, TIMESTAMP, func, SmallInteger, Integer
from sqlalchemy.dialects.mysql import TINYINT, INTEGER

from backend.vidmuse.core.database import Base


class Material(Base):
    """素材库模型"""
    __tablename__ = "materials"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    type = Column(TINYINT, nullable=False, comment="素材类型 1-图片 2-视频 3-音频")
    title = Column(VARCHAR(200), comment="素材标题")
    url = Column(VARCHAR(500), nullable=False, comment="存储URL")
    file_size = Column(BigInteger, comment="文件大小(字节)")
    duration = Column(INTEGER, comment="时长(视频/音频)")
    format = Column(VARCHAR(20), comment="文件格式")
    ai_features = Column(JSON, comment="AI特征向量/描述（用于智能检索）")
    source_type = Column(TINYINT, default=1, comment="来源 1-上传 2-AI生成 3-爬取 4-购买")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), comment="创建时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "url": self.url,
            "file_size": self.file_size,
            "duration": self.duration,
            "format": self.format,
            "ai_features": self.ai_features,
            "source_type": self.source_type,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }