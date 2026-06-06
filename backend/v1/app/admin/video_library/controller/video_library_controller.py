"""视频素材库API接口"""
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from backend.store.database.async_database import get_db
from backend.framework.web.response import Response
from backend.framework.web.auth import admin_required  # 管理员权限校验
from backend.v1.app.admin.video_library.service.video_library_service import VideoLibraryService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/video-library", tags=["video-library"])
video_service = VideoLibraryService()


# 请求模型
class VideoCreateRequest(BaseModel):
    """手动创建视频请求"""
    title: Optional[str] = Field(None, description="视频标题")
    description: Optional[str] = Field(None, description="视频描述")
    url: str = Field(..., description="视频URL")
    cover_url: Optional[str] = Field(None, description="封面URL")
    duration: Optional[int] = Field(None, description="时长(秒)")
    format: Optional[str] = Field(None, description="文件格式")
    hot_score: Optional[int] = Field(None, ge=0, le=100, description="爆款分数(0-100)")
    category: Optional[str] = Field(None, description="分类名称")
    category_id: Optional[int] = Field(None, description="分类ID，关联product_categories表（仅支持三级分类）")
    tags: Optional[List[str]] = Field(None, description="标签列表")


class VideoUpdateRequest(BaseModel):
    """更新视频请求"""
    title: Optional[str] = Field(None, description="视频标题")
    description: Optional[str] = Field(None, description="视频描述")
    cover_url: Optional[str] = Field(None, description="封面URL")
    duration: Optional[int] = Field(None, description="时长(秒)")
    hot_score: Optional[int] = Field(None, ge=0, le=100, description="爆款分数(0-100)")
    category: Optional[str] = Field(None, description="分类名称")
    category_id: Optional[int] = Field(None, description="分类ID，关联product_categories表（仅支持三级分类），传null清空关联")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    parsed_data: Optional[Dict] = Field(None, description="解析数据")


class BatchImportHotRequest(BaseModel):
    """批量导入爆款视频请求"""
    category: Optional[str] = Field(None, description="商品品类名称")
    category_id: Optional[int] = Field(None, description="分类ID，关联product_categories表（仅支持三级分类），优先级高于category")
    min_hot_score: int = Field(80, ge=0, le=100, description="最低爆款分数")
    start_time: Optional[int] = Field(None, description="开始时间(UTC时间戳)")
    end_time: Optional[int] = Field(None, description="结束时间(UTC时间戳)")
    limit: Optional[int] = Field(None, ge=1, description="最大导入数量")


@router.get("/", summary="分页查询视频列表")
async def list_videos(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(None, description="分类名称"),
    category_id: Optional[int] = Query(None, description="分类ID，关联product_categories表"),
    min_hot_score: Optional[int] = Query(None, ge=0, le=100, description="最低爆款分数"),
    source_type: Optional[int] = Query(None, description="来源类型"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[int] = Query(None, ge=0, le=3, description="处理状态：0待处理 1处理中 2已完成 3失败"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),  # 管理员权限校验
):
    videos, total = await video_service.get_video_list(
        db, page, page_size, category, category_id, min_hot_score, source_type, keyword, status
    )
    return Response.success(data={
        "list": videos,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.get("/{video_id}", summary="获取视频详情")
async def get_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    video = await video_service.get_video_detail(db, video_id)
    if not video:
        return Response.error(message="视频不存在")
    return Response.success(data=video)


@router.post("/", summary="手动创建视频记录")
async def create_video(
    request: VideoCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    try:
        video = await video_service.create_video(
            db,
            created_by=current_user_id,
            **request.dict(exclude_unset=True)
        )
        return Response.success(data=video)
    except HTTPException as e:
        return Response.error(code=e.status_code, message=e.detail)


@router.post("/upload", summary="上传视频文件")
async def upload_video(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    tags: Optional[List[str]] = Form(None),
    trigger_ai_parse: bool = Form(True, description="是否触发AI解析，默认True"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    video = await video_service.upload_video(
        db,
        file=file,
        created_by=current_user_id,
        title=title,
        description=description,
        category=category,
        category_id=category_id,
        tags=tags,
        trigger_ai_parse=trigger_ai_parse
    )
    return Response.success(data=video)


@router.put("/{video_id}", summary="更新视频信息")
async def update_video(
    video_id: int,
    request: VideoUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    video = await video_service.update_video(
        db,
        video_id,
        **request.dict(exclude_unset=True)
    )
    if not video:
        return Response.error(message="视频不存在")
    return Response.success(data=video)


@router.delete("/{video_id}", summary="删除视频")
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    success = await video_service.delete_video(db, video_id)
    if not success:
        return Response.error(message="视频不存在")
    return Response.success(message="删除成功")


@router.post("/{video_id}/parse", summary="手动触发视频解析")
async def trigger_parsing(
    video_id: int,
    force: bool = Query(False, description="是否强制重新解析，即使已经解析过"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    success = await video_service.trigger_parsing(db, video_id, force=force)
    if not success:
        return Response.error(message="视频不存在或未关联资产")
    return Response.success(message="解析任务已触发")


@router.get("/{video_id}/parsing-progress", summary="查询视频解析进度")
async def get_parsing_progress(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    progress = await video_service.get_parsing_progress(db, video_id)
    if not progress:
        return Response.error(message="视频不存在或未关联资产")
    return Response.success(data=progress)


@router.get("/{video_id}/slices", summary="获取视频对应的切片列表")
async def get_video_slices(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    slices = await video_service.get_video_slices(db, video_id)
    return Response.success(data=slices)


@router.post("/batch-import-hot", summary="批量导入爆款视频")
async def batch_import_hot(
    request: BatchImportHotRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    result = await video_service.batch_import_hot_reports(
        db,
        created_by=current_user_id,
        **request.dict(exclude_unset=True)
    )
    return Response.success(data=result)
