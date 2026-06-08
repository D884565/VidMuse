"""
流水线任务API控制器
"""
from fastapi import APIRouter, Depends, Query, Body, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, HttpUrl

from backend.store.database.async_database import get_db
from backend.v1.app.task_scheduler.service.task_service import task_service
from backend.v1.app.task_scheduler.dto.task_schema import (
    TaskSubmitRequest, TaskSubmitResponse, TaskTypeEnum
)

router = APIRouter(prefix="/pipeline", tags=["流水线任务"])


# ==================== DTO定义 ====================

class MultimodalContentItem(BaseModel):
    """多模态内容项"""
    type: str = Field(..., description="内容类型：text/image_url/video", example="text")
    text: Optional[str] = Field(None, description="文本内容，type为text时必填")
    image_url: Optional[Dict[str, Any]] = Field(None, description="图片URL信息，type为image_url时必填")
    video_url: Optional[str] = Field(None, description="视频URL，type为video时必填")


class ProductParsingSubmitRequest(BaseModel):
    """商品解析任务提交请求"""
    product_id: str = Field(..., description="商品ID", example="prod_001")
    multimodal_content: List[MultimodalContentItem] = Field(
        ...,
        description="多模态内容列表，支持text、image_url、video类型",
        example=[
            {"type": "text", "text": "这是一款粉色碎花连衣裙，收腰设计，面料舒适，现价159元"},
            {"type": "image_url", "image_url": {"url": "https://example.com/product.jpg"}}
        ]
    )
    product_schema_path: Optional[str] = Field(None, description="自定义商品校验Schema路径")
    persist_to_asset: bool = Field(True, description="是否将结果落库到asset表")
    user_id: Optional[int] = Field(None, description="关联用户ID", example=1)
    priority: int = Field(default=3, ge=1, le=5, description="优先级（1-5，越小优先级越高）", example=3)


class DirectVideoParsingSubmitRequest(BaseModel):
    """直接视频解析任务提交请求"""
    video_url: HttpUrl = Field(..., description="视频公网可访问URL", example="https://example.com/video.mp4")
    video_id: str = Field(..., description="视频ID", example="vid_123456")
    asset_id: int = Field(..., description="关联资产ID", example=1001)
    video_duration: int = Field(..., description="视频时长，单位毫秒", example=120000)
    slice_schema_path: Optional[str] = Field(None, description="自定义切片校验Schema路径")
    video_schema_path: Optional[str] = Field(None, description="自定义视频整体校验Schema路径")
    enable_vectorization: bool = Field(True, description="是否启用向量化存储")
    user_id: Optional[int] = Field(None, description="关联用户ID", example=1)
    priority: int = Field(default=3, ge=1, le=5, description="优先级（1-5，越小优先级越高）", example=3)


# ==================== API接口 ====================

@router.post(
    "/product-parsing/submit",
    response_model=TaskSubmitResponse,
    summary="提交商品解析任务"
)
async def submit_product_parsing_task(
    request: ProductParsingSubmitRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    提交商品解析异步任务
    支持多模态输入：图片、文本、视频的任意组合
    """
    # 构建任务payload
    payload = {
        "product_id": request.product_id,
        "multimodal_content": [item.dict(exclude_none=True) for item in request.multimodal_content],
        "product_schema_path": request.product_schema_path,
        "persist_to_asset": request.persist_to_asset,
        "user_id": request.user_id
    }

    # 提交任务
    result = await task_service.submit_task(
        db=db,
        task_request=TaskSubmitRequest(
            task_type=TaskTypeEnum.PRODUCT_PARSING,
            payload=payload,
            priority=request.priority,
            user_id=request.user_id
        )
    )

    return result


@router.post(
    "/direct-video-parsing/submit",
    response_model=TaskSubmitResponse,
    summary="提交直接视频解析任务"
)
async def submit_direct_video_parsing_task(
    request: DirectVideoParsingSubmitRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    提交直接视频解析异步任务
    流程：完整视频URL → 大模型直接理解 → 输出结构化数据 → 校验 → 向量化 → 落库
    """
    # 构建任务payload
    payload = {
        "video_url": str(request.video_url),
        "video_id": request.video_id,
        "asset_id": request.asset_id,
        "video_duration": request.video_duration,
        "slice_schema_path": request.slice_schema_path,
        "video_schema_path": request.video_schema_path,
        "enable_vectorization": request.enable_vectorization,
        "user_id": request.user_id
    }

    # 提交任务
    result = await task_service.submit_task(
        db=db,
        task_request=TaskSubmitRequest(
            task_type=TaskTypeEnum.DIRECT_VIDEO_PARSING,
            payload=payload,
            priority=request.priority,
            user_id=request.user_id
        )
    )

    return result
