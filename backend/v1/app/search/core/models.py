# backend/v1/app/search/core/models.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class SearchQuery:
    """检索查询对象"""
    query_text: str  # 查询文本
    top_k: int = 10  # 返回结果数量
    filters: Dict[str, Any] = field(default_factory=dict)  # 过滤条件
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据（用户ID、项目ID、会话ID等）
    query_embedding: Optional[List[float]] = None  # 查询向量（如果已经生成）
    required_channels: Optional[List[str]] = None  # 指定要使用的渠道，None表示使用所有启用的渠道
    timeout: int = 30  # 超时时间（秒）

@dataclass
class SearchResult:
    """统一检索结果"""
    result_id: str  # 结果唯一ID
    content: str  # 结果内容
    score: float  # 相关性得分（0-1）
    source: str  # 来源渠道
    source_type: str  # 来源类型（document, faq, product等）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据
    created_at: datetime = field(default_factory=datetime.now)  # 结果生成时间
