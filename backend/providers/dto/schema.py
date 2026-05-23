from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """对话消息"""
    role: str = Field(description="角色，可选值：user, assistant, system")
    content: str = Field(description="消息内容")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"role": "user", "content": "你好，请介绍一下你自己"}
            ]
        }
    }


class VideoRequest(BaseModel):
    """视频请求"""
    model: Optional[str] = Field(None, description="模型名称，不指定则使用默认模型")
    ratio: Optional[str] = Field(None, description="视频比例")
    duration: Optional[int] = Field(None, description="视频时长")
    resolution: Optional[str] = Field(None, description="视频分辨率")
    generate_audio: Optional[bool] = Field(False, description="是否生成音频")
    draft: Optional[bool] = Field(False, description="是否生成草稿")
    watermark: Optional[bool] = Field(False, description="是否添加水印")
    return_last_frame: Optional[bool] = Field(False, description="是否返回最后一帧")




class ChatRequest(BaseModel):
    """对话请求"""
    messages: List[ChatMessage] = Field(description="对话历史")
    model: Optional[str] = Field(None, description="模型名称，不指定则使用默认模型")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数，控制生成的随机性")
    max_tokens: Optional[int] = Field(2048, ge=1, description="最大生成token数")
    top_p: Optional[float] = Field(0.9, ge=0.0, le=1.0, description="核采样参数")
    stream: Optional[bool] = Field(False, description="是否使用流式响应")
    extra_params: Optional[Dict[str, Any]] = Field(None, description="额外的模型参数")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {"role": "user", "content": "你好，请介绍一下你自己"}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1024
                }
            ]
        }
    }


class ChatUsage(BaseModel):
    """Token使用情况"""
    prompt_tokens: int = Field(description="输入token数")
    completion_tokens: int = Field(description="输出token数")
    total_tokens: int = Field(description="总token数")


class ChatResponse(BaseModel):
    """对话响应"""
    content: str = Field(description="生成的内容")
    role: str = Field(description="角色，通常是assistant")
    usage: ChatUsage = Field(description="token使用情况")
    model: str = Field(description="使用的模型名称")
    id: Optional[str] = Field(None, description="请求ID")
    finish_reason: Optional[str] = Field(None, description="结束原因")


class EmbeddingRequest(BaseModel):
    """嵌入请求"""
    texts: List[str] = Field(description="待嵌入的文本列表")
    model: Optional[str] = Field(None, description="嵌入模型名称，不指定则使用默认模型")
    extra_params: Optional[Dict[str, Any]] = Field(None, description="额外的参数")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"text":"天很蓝，海很深","type":"text"},
                {"image_url":{"url":"https://ark-project.tos-cn-beijing.volces.com/images/view.jpeg"},"type":"image_url"},

            ]

        }
    }


class EmbeddingUsage(BaseModel):
    """嵌入Token使用情况"""
    prompt_tokens: int = Field(description="输入token数")
    total_tokens: int = Field(description="总token数")


class EmbeddingResponse(BaseModel):
    """嵌入响应"""
    embeddings: List[List[float]] = Field(description="嵌入向量列表，顺序与输入一致")
    usage: EmbeddingUsage = Field(description="token使用情况")
    model: str = Field(description="使用的模型名称")


class VideoResponse(BaseModel):
    """视频生成响应"""
    video_url: str = Field(description="生成的视频URL")
    duration: Optional[float] = Field(None, description="实际生成的视频时长(秒)")
    id: str = Field(description="视频生成任务ID")
    model: str = Field(description="使用的模型名称")
    status: str = Field(description="任务状态")
    resolution: Optional[str] = Field(None, description="视频分辨率")
    ratio: Optional[str] = Field(None, description="视频比例")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "video_url": "https://example.com/video.mp4",
                    "duration": 10.5,
                    "id": "task_123456",
                    "model": "seedance-1.5",
                    "status": "succeeded",
                    "resolution": "1920x1080",
                    "ratio": "16:9"
                }
            ]
        }
    }


class ImageUnderstandingRequest(BaseModel):
    """图片理解请求"""
    image_url: str = Field(description="图片URL")
    prompt: Optional[str] = Field("请描述这张图片的内容", description="理解提示词")
    model: Optional[str] = Field(None, description="模型名称，不指定则使用默认多模态模型")
    max_tokens: Optional[int] = Field(2048, description="最大生成token数")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    top_p: Optional[float] = Field(0.9, ge=0.0, le=1.0, description="核采样参数")


class ImageUnderstandingResponse(BaseModel):
    """图片理解响应"""
    content: str = Field(description="图片理解结果")
    usage: ChatUsage = Field(description="token使用情况")
    model: str = Field(description="使用的模型名称")
    id: Optional[str] = Field(None, description="请求ID")


class VideoUnderstandingRequest(BaseModel):
    """视频理解请求"""
    video_url: str = Field(description="视频URL")
    prompt: Optional[str] = Field("请描述这个视频的内容", description="理解提示词")
    model: Optional[str] = Field(None, description="模型名称，不指定则使用默认视频理解模型")
    max_tokens: Optional[int] = Field(2048, description="最大生成token数")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    top_p: Optional[float] = Field(0.9, ge=0.0, le=1.0, description="核采样参数")


class VideoUnderstandingResponse(BaseModel):
    """视频理解响应"""
    content: str = Field(description="视频理解结果")
    usage: ChatUsage = Field(description="token使用情况")
    model: str = Field(description="使用的模型名称")
    id: Optional[str] = Field(None, description="请求ID")


class TextUnderstandingRequest(BaseModel):
    """文本理解请求"""
    text: str = Field(description="待理解的文本内容")
    prompt: Optional[str] = Field("请分析这段文本的内容", description="理解提示词")
    model: Optional[str] = Field(None, description="模型名称，不指定则使用默认模型")
    max_tokens: Optional[int] = Field(2048, description="最大生成token数")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    top_p: Optional[float] = Field(0.9, ge=0.0, le=1.0, description="核采样参数")


class TextUnderstandingResponse(BaseModel):
    """文本理解响应"""
    content: str = Field(description="文本理解结果")
    usage: ChatUsage = Field(description="token使用情况")
    model: str = Field(description="使用的模型名称")
    id: Optional[str] = Field(None, description="请求ID")
