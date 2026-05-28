from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class Message(BaseModel):
    """消息对象"""
    role: str = Field(description="角色，可选值：user, assistant, system, tool")
    content: str = Field(description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="消息时间戳")
    tool_call: Optional[Dict[str, Any]] = Field(None, description="工具调用信息")
    tool_result: Optional[Dict[str, Any]] = Field(None, description="工具返回结果")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "role": "user",
                    "content": "什么是向量数据库？",
                    "timestamp": "2024-01-01T12:00:00"
                }
            ]
        }
    }




class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str = Field(description="会话ID")
    answer: str = Field(description="回答内容")
    is_tool_call: bool = Field(False, description="是否调用了工具")
    tool_name: Optional[str] = Field(None, description="调用的工具名称（单工具调用时）")
    tool_params: Optional[Dict[str, Any]] = Field(None, description="工具调用参数（单工具调用时）")
    tool_result: Optional[str] = Field(None, description="工具返回结果（单工具调用时）")
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据（迭代次数、多工具调用信息等）")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "session_abc123def456",
                    "answer": "向量数据库是一种专门用于存储和查询向量数据的数据库系统...",
                    "is_tool_call": True,
                    "tool_name": "rag_search",
                    "tool_params": {
                        "query": "什么是向量数据库？",
                        "top_k": 10
                    },
                    "timestamp": "2024-01-01T12:00:01"
                }
            ]
        }
    }


class SessionHistoryResponse(BaseModel):
    """会话历史响应"""
    session_id: str = Field(description="会话ID")
    messages: List[Message] = Field(description="消息历史列表")
    created_at: datetime = Field(description="会话创建时间")
    updated_at: datetime = Field(description="最后更新时间")
