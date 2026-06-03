from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, File, Form, UploadFile, Path, Body, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from backend.framework.web.response import Response
from backend.store.database.sync_database import get_db
from backend.store.database.async_database import get_db as get_async_db
from backend.framework.web.auth import admin_required
from backend.v1.app.assets.service import AssetService
from backend.v1.app.video_library.service.video_library_service import VideoLibraryService

router = APIRouter(prefix="/assets", tags=["资产管理"])


@router.post("/upload", response_model=Response, summary="用户端上传素材/资产")
async def upload_asset(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(..., description="上传的文件"),
        type: int = Form(..., description="资产类型：1-图片, 2-视频, 3-音频"),
        title: Optional[str] = Form(None, description="资产标题"),
        source_type: int = Form(0, description="来源：0-用户上传, 1-AI生成, 2-爬取, 3-购买"),
        skip_analysis: bool = Form(False, description="是否跳过AI解析，默认不跳过"),
        db: Session = Depends(get_db)
):
    """【面向用户】上传视频/图片/音频素材到个人素材库"""
    result = await AssetService.upload_user_asset(
        db=db,
        background_tasks=background_tasks,
        file=file,
        type=type,
        title=title,
        source_type=source_type,
        skip_analysis=skip_analysis
    )
    return Response.success(data=result, message="上传成功")


@router.post("/upload/internal", response_model=Response, summary="后台内部上传素材/资产")
async def upload_internal_asset(
        file: UploadFile = File(..., description="上传的文件"),
        type: int = Form(..., description="资产类型：1-图片, 2-视频, 3-音频"),
        title: Optional[str] = Form(None, description="资产标题"),
        source_type: Optional[int] = Form(1, description="来源：0-上传, 1-AI生成, 2-系统预置, 3-其他"),
        skip_ai_analysis: Optional[bool] = Form(True, description="是否跳过AI特征分析"),
        db: Session = Depends(get_db)
):
    """【后台内部使用】上传系统内部资产，支持跳过AI分析提高速度"""
    result = await AssetService.upload_internal_asset(
        db=db,
        file=file,
        type=type,
        title=title,
        source_type=source_type,
        skip_ai_analysis=skip_ai_analysis
    )
    return Response.success(data=result, message="内部资产上传成功")


@router.get("", response_model=Response, summary="获取资产列表")
def list_assets(
        type: Optional[int] = None,
        source_type: Optional[int] = None,
        keyword: Optional[str] = None,
        format: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
):
    """获取当前用户的资产列表"""
    result = AssetService.list_assets(
        db=db,
        type=type,
        source_type=source_type,
        keyword=keyword,
        format=format,
        page=page,
        page_size=page_size
    )
    return Response.success(data=result)


@router.get("/{asset_id}", response_model=Response, summary="获取资产详情")
def get_asset_detail(
        asset_id: int = Path(..., description="资产ID"),
        db: Session = Depends(get_db)
):
    """获取资产详细信息"""
    result = AssetService.get_asset_detail(db=db, asset_id=asset_id)
    return Response.success(data=result)


@router.put("/{asset_id}", response_model=Response, summary="更新资产信息")
def update_asset(
        asset_id: int = Path(..., description="资产ID"),
        title: Optional[str] = Body(None, description="资产标题"),
        ai_features: Optional[dict] = Body(None, description="AI特征因子"),
        db: Session = Depends(get_db)
):
    """更新资产标题等信息"""
    result = AssetService.update_asset(
        db=db,
        asset_id=asset_id,
        title=title,
        ai_features=ai_features
    )
    return Response.success(data=result, message="更新成功")


@router.post("/{asset_id}/parse", response_model=Response, summary="手动触发资产解析")
async def parse_asset(
        asset_id: int = Path(..., description="资产ID"),
        force: bool = Body(False, description="是否强制重新解析，即使已经解析过"),
        db: Session = Depends(get_db)
):
    """手动触发已上传资产的AI解析，支持强制重新解析"""
    result = await AssetService.parse_asset(db=db, asset_id=asset_id, force=force)
    return Response.success(data=result, message="解析任务已启动")


@router.get("/{asset_id}/parsing-progress", response_model=Response, summary="查询资产解析进度")
def get_parsing_progress(
        asset_id: int = Path(..., description="资产ID"),
        db: Session = Depends(get_db)
):
    """查询资产解析的进度和状态"""
    result = AssetService.get_parsing_progress(db=db, asset_id=asset_id)
    return Response.success(data=result)


@router.post("/{asset_id}/retry-parsing", response_model=Response, summary="重试失败的资产解析")
async def retry_parsing(
        asset_id: int = Path(..., description="资产ID"),
        db: Session = Depends(get_db)
):
    """重试失败的资产解析，支持从断点处恢复执行"""
    result = await AssetService.retry_parsing(db=db, asset_id=asset_id)
    return Response.success(data=result, message="重试解析任务已启动")




@router.delete("/{asset_id}", response_model=Response, summary="删除资产")
def delete_asset(
        asset_id: int = Path(..., description="资产ID"),
        db: Session = Depends(get_db)
):
    """删除资产（会级联删除所有关联切片）"""
    AssetService.delete_asset(db=db, asset_id=asset_id)
    return Response.success(data=None, message="删除成功")


# ==================== 管理员专属：内部视频素材库接口 ====================
video_library_service = VideoLibraryService()


@router.get("/admin/video-library", response_model=Response, summary="【管理员】查询内部视频库列表")
async def list_video_library(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(None, description="分类"),
    min_hot_score: Optional[int] = Query(None, ge=0, le=100, description="最低爆款分数"),
    source_type: Optional[int] = Query(None, description="来源类型"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】分页查询内部视频素材库列表"""
    videos, total = await video_library_service.get_video_list(
        db, page, page_size, category, min_hot_score, source_type, keyword
    )
    return Response.success(data={
        "list": videos,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.get("/admin/video-library/{video_id}", response_model=Response, summary="【管理员】获取内部视频详情")
async def get_video_library_detail(
    video_id: int = Path(..., description="视频ID"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】获取内部视频素材详情"""
    video = await video_library_service.get_video_detail(db, video_id)
    if not video:
        return Response.error(message="视频不存在")
    return Response.success(data=video)


@router.post("/admin/video-library", response_model=Response, summary="【管理员】手动创建内部视频记录")
async def create_video_library(
    title: Optional[str] = Body(None, description="视频标题"),
    description: Optional[str] = Body(None, description="视频描述"),
    url: str = Body(..., description="视频URL"),
    cover_url: Optional[str] = Body(None, description="封面URL"),
    duration: Optional[int] = Body(None, description="时长(秒)"),
    format: Optional[str] = Body(None, description="文件格式"),
    hot_score: Optional[int] = Body(None, ge=0, le=100, description="爆款分数(0-100)"),
    category: Optional[str] = Body(None, description="分类"),
    tags: Optional[List[str]] = Body(None, description="标签列表"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】手动录入内部视频素材记录"""
    try:
        video = await video_library_service.create_video(
            db,
            created_by=admin_user_id,
            title=title,
            description=description,
            url=url,
            cover_url=cover_url,
            duration=duration,
            format=format,
            hot_score=hot_score,
            category=category,
            tags=tags
        )
        return Response.success(data=video)
    except Exception as e:
        return Response.error(message=str(e))


@router.post("/admin/video-library/upload", response_model=Response, summary="【管理员】上传视频到内部素材库")
async def upload_video_to_library(
    file: UploadFile = File(..., description="上传的视频文件"),
    title: Optional[str] = Form(None, description="视频标题"),
    description: Optional[str] = Form(None, description="视频描述"),
    category: Optional[str] = Form(None, description="分类"),
    tags: Optional[List[str]] = Form(None, description="标签列表"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】上传视频文件到内部素材库，自动触发解析"""
    video = await video_library_service.upload_video(
        db,
        file=file,
        created_by=admin_user_id,
        title=title,
        description=description,
        category=category,
        tags=tags
    )
    return Response.success(data=video, message="上传成功")


@router.put("/admin/video-library/{video_id}", response_model=Response, summary="【管理员】更新内部视频信息")
async def update_video_library(
    video_id: int = Path(..., description="视频ID"),
    title: Optional[str] = Body(None, description="视频标题"),
    description: Optional[str] = Body(None, description="视频描述"),
    cover_url: Optional[str] = Body(None, description="封面URL"),
    duration: Optional[int] = Body(None, description="时长(秒)"),
    hot_score: Optional[int] = Body(None, ge=0, le=100, description="爆款分数(0-100)"),
    category: Optional[str] = Body(None, description="分类"),
    tags: Optional[List[str]] = Body(None, description="标签列表"),
    parsed_data: Optional[Dict] = Body(None, description="解析数据"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】更新内部视频素材信息"""
    update_data = {}
    if title is not None:
        update_data["title"] = title
    if description is not None:
        update_data["description"] = description
    if cover_url is not None:
        update_data["cover_url"] = cover_url
    if duration is not None:
        update_data["duration"] = duration
    if hot_score is not None:
        update_data["hot_score"] = hot_score
    if category is not None:
        update_data["category"] = category
    if tags is not None:
        update_data["tags"] = tags
    if parsed_data is not None:
        update_data["parsed_data"] = parsed_data

    video = await video_library_service.update_video(db, video_id, **update_data)
    if not video:
        return Response.error(message="视频不存在")
    return Response.success(data=video, message="更新成功")


@router.delete("/admin/video-library/{video_id}", response_model=Response, summary="【管理员】删除内部视频")
async def delete_video_library(
    video_id: int = Path(..., description="视频ID"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】删除内部视频素材（不会删除关联的资产和切片）"""
    success = await video_library_service.delete_video(db, video_id)
    if not success:
        return Response.error(message="视频不存在")
    return Response.success(message="删除成功")


@router.get("/admin/video-library/{video_id}/slices", response_model=Response, summary="【管理员】获取视频对应的切片列表")
async def get_video_library_slices(
    video_id: int = Path(..., description="视频ID"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】获取内部视频对应的切片列表"""
    slices = await video_library_service.get_video_slices(db, video_id)
    return Response.success(data=slices)


@router.post("/admin/video-library/{video_id}/parse", response_model=Response, summary="【管理员】手动触发视频解析")
async def trigger_video_library_parsing(
    video_id: int = Path(..., description="视频ID"),
    force: bool = Query(False, description="是否强制重新解析，即使已经解析过"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】手动触发内部视频解析任务"""
    success = await video_library_service.trigger_parsing(db, video_id, force=force)
    if not success:
        return Response.error(message="视频不存在或未关联资产")
    return Response.success(message="解析任务已触发")


@router.post("/admin/video-library/batch-import-hot", response_model=Response, summary="【管理员】批量导入爆款视频")
async def batch_import_hot_videos(
    category: Optional[str] = Body(None, description="商品品类"),
    min_hot_score: int = Body(80, ge=0, le=100, description="最低爆款分数"),
    start_time: Optional[int] = Body(None, description="开始时间(UTC时间戳)"),
    end_time: Optional[int] = Body(None, description="结束时间(UTC时间戳)"),
    limit: Optional[int] = Body(None, ge=1, description="最大导入数量"),
    db: AsyncSession = Depends(get_async_db),
    admin_user_id: int = Depends(admin_required),
):
    """【管理员专属】批量导入爆款视频到内部素材库"""
    result = await video_library_service.batch_import_hot_reports(
        db,
        created_by=admin_user_id,
        category=category,
        min_hot_score=min_hot_score,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
    return Response.success(data=result)


