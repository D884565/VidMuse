from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, Path, Body, BackgroundTasks
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.store.database.sync_database import get_db
from backend.v1.app.rag.service.asset_service import AssetService

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


