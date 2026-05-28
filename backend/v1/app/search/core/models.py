from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class Query:
    """查询对象"""
    text: str  # 原始查询文本
    intent: Optional[str] = None  # 识别到的查询意图
    enhanced_text: Optional[str] = None  # 增强后的查询文本
    expanded_keywords: List[str] = field(default_factory=list)  # 扩展的关键词列表
    retrieval_type: Optional[str] = None  # 要使用的检索方式
    required_sources: List[str] = field(default_factory=list)  # 指定检索的数据源
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

@dataclass
class Document:
    """检索到的文档对象"""
    id: str  # 文档唯一标识
    content: str  # 文档内容
    score: float  # 相似度得分
    source: str  # 数据源类型（vector/keyword/sql/api）
    source_type: str  # 具体数据源（milvus/es/mysql等）
    title: Optional[str] = None  # 文档标题
    url: Optional[str] = None  # 文档链接
    metadata: Dict[str, Any] = field(default_factory=dict)  # 文档元数据

@dataclass
class SearchContext:
    """检索上下文"""
    conversation_history: List[Dict[str, str]] = field(default_factory=list)  # 对话历史，格式: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    user_id: Optional[str] = None  # 用户ID
    session_id: Optional[str] = None  # 会话ID
    top_k: int = 10  # 返回结果数量
    timeout: int = 10  # 检索超时时间
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外上下文信息

@dataclass
class SearchResult:
    """检索结果"""
    query: Query  # 处理后的查询对象
    documents: List[Document]  # 最终检索结果
    context: SearchContext  # 检索上下文
    cost_time: float  # 检索耗时（秒）
    success: bool = True  # 是否检索成功
    error_msg: Optional[str] = None  # 错误信息
    retrieval_metadata: Dict[str, Any] = field(default_factory=dict)  # 检索过程元数据（各数据源返回情况等）
