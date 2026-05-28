from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    user_id: Optional[str] = Field(None, description="用户ID，用于关联用户的会话列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="会话元数据，可存储自定义信息")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user_123",
                    "metadata": {
                        "platform": "web",
                        "version": "1.0.0"
                    }
                }
            ]
        }
    }


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str = Field(description="会话ID")
    message: str = Field(description="用户消息内容")
    stream: Optional[bool] = Field(False, description="是否使用流式响应")
    tool_call_enabled: Optional[bool] = Field(True, description="是否启用工具调用")
    extra_params: Optional[Dict[str, Any]] = Field(None, description="额外参数")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "session_abc123",
                    "message": "什么是向量数据库？",
                    "stream": False
                }
            ]
        }
    }
