from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, Path, UploadFile
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.store.database.sync_database import get_db
from backend.v1.app.assets.service.asset_service import AssetService
from backend.framework.web.auth import get_current_user_id, get_current_user_payload, admin_required

router = APIRouter(prefix="/assets", tags=["Asset Management"])


@router.post("/text", response_model=Response, summary="Create text material")
def create_text_asset(
    title: Optional[str] = Body(None, description="Asset title"),
    content_text: str = Body(..., description="Text material content"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    result = AssetService.create_text_asset(db=db, user_id=current_user_id, title=title, content_text=content_text)
    return Response.success(data=result, message="Created successfully")


@router.put("/{asset_id}/text", response_model=Response, summary="Update text material")
def update_text_asset(
    asset_id: int = Path(..., description="Asset ID"),
    title: Optional[str] = Body(None, description="Asset title"),
    content_text: str = Body(..., description="Text material content"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    result = AssetService.update_text_asset(
        db=db,
        user_id=current_user_id,
        asset_id=asset_id,
        title=title,
        content_text=content_text,
    )
    return Response.success(data=result, message="Updated successfully")


@router.post("/upload", response_model=Response, summary="Upload user asset")
async def upload_asset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    type: int = Form(..., description="Asset type: 1-image, 2-video, 3-audio"),
    title: Optional[str] = Form(None, description="Asset title"),
    source_type: int = Form(0, description="Source type"),
    skip_analysis: bool = Form(False, description="Skip AI parsing"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    result = await AssetService.upload_user_asset(
        db=db,
        background_tasks=background_tasks,
        file=file,
        type=type,
        title=title,
        source_type=source_type,
        skip_analysis=skip_analysis,
        user_id=current_user_id,
    )
    return Response.success(data=result, message="Uploaded successfully")




@router.post("/upload/internal", response_model=Response, summary="Upload internal asset")
async def upload_internal_asset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    type: int = Form(..., description="Asset type: 1-image, 2-video, 3-audio"),
    title: Optional[str] = Form(None, description="Asset title"),
    source_type: Optional[int] = Form(1, description="Source type"),
    skip_ai_analysis: bool = Form(True, description="Skip AI parsing"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    result = await AssetService.upload_internal_asset(
        db=db,
        background_tasks=background_tasks,
        file=file,
        type=type,
        title=title,
        source_type=source_type,
        skip_ai_analysis=skip_ai_analysis,
        user_id=current_user_id,
    )
    return Response.success(data=result, message="Internal asset uploaded successfully")


@router.post("/{asset_id}/reupload", response_model=Response, summary="Directly reupload image asset")
async def reupload_image_asset(
    asset_id: int = Path(..., description="Asset ID"),
    file: UploadFile = File(..., description="Image file to replace the current asset"),
    title: Optional[str] = Form(None, description="Asset title"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    result = await AssetService.reupload_image_asset(
        db=db,
        user_id=current_user_id,
        asset_id=asset_id,
        file=file,
        title=title,
    )
    return Response.success(data=result, message="Reuploaded successfully")




@router.get("", response_model=Response, summary="List assets")
def list_assets(
    type: Optional[int] = None,
    source_type: Optional[int] = None,
    keyword: Optional[str] = None,
    format: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user_payload: dict = Depends(get_current_user_payload),
):
    user_id = int(current_user_payload["sub"])
    user_role = current_user_payload.get("role")

    # 管理员可以查看所有资产，普通用户只能查看自己的
    query_user_id = user_id if user_role != 0 else None

    result = AssetService.list_assets(
        db=db,
        user_id=query_user_id,
        type=type,
        source_type=source_type,
        keyword=keyword,
        format=format,
        page=page,
        page_size=page_size,
    )
    return Response.success(data=result)


@router.get("/{asset_id}", response_model=Response, summary="Get asset detail")
def get_asset_detail(
    asset_id: int = Path(..., description="Asset ID"),
    db: Session = Depends(get_db),
    current_user_payload: dict = Depends(get_current_user_payload),
):
    user_id = int(current_user_payload["sub"])
    user_role = current_user_payload.get("role")

    # 管理员可以查看所有资产，普通用户只能查看自己的
    query_user_id = user_id if user_role != 0 else None

    result = AssetService.get_asset_detail(db=db, user_id=query_user_id, asset_id=asset_id)
    return Response.success(data=result)


@router.put("/{asset_id}", response_model=Response, summary="Update asset")
def update_asset(
    asset_id: int = Path(..., description="Asset ID"),
    title: Optional[str] = Body(None, description="Asset title"),
    ai_features: Optional[dict] = Body(None, description="AI feature payload"),
    db: Session = Depends(get_db),
    current_user_payload: dict = Depends(get_current_user_payload),
):
    user_id = int(current_user_payload["sub"])
    user_role = current_user_payload.get("role")

    # 管理员可以更新所有资产，普通用户只能更新自己的
    query_user_id = user_id if user_role != 0 else None

    result = AssetService.update_asset(
        db=db,
        user_id=query_user_id,
        asset_id=asset_id,
        title=title,
        ai_features=ai_features,
    )
    return Response.success(data=result, message="Updated successfully")


@router.post("/{asset_id}/parse", response_model=Response, summary="Parse asset")
async def parse_asset(
    asset_id: int = Path(..., description="Asset ID"),
    force: bool = Body(False, description="Force re-parse"),
    product_id: Optional[int] = Body(None, description="关联的产品ID，用于建立资产和产品的关联"),
    db: Session = Depends(get_db),
    current_user_payload: dict = Depends(get_current_user_payload),
):
    user_id = int(current_user_payload["sub"])
    user_role = current_user_payload.get("role")

    # 管理员可以解析所有资产，普通用户只能解析自己的
    query_user_id = user_id if user_role != 0 else None

    result = await AssetService.parse_asset(db=db, user_id=query_user_id, asset_id=asset_id, force=force, product_id=product_id)
    return Response.success(data=result, message="Parse task started")


@router.get("/{asset_id}/parsing-progress", response_model=Response, summary="Get parsing progress")
def get_parsing_progress(
    asset_id: int = Path(..., description="Asset ID"),
    db: Session = Depends(get_db),
    current_user_payload: dict = Depends(get_current_user_payload),
):
    user_id = int(current_user_payload["sub"])
    user_role = current_user_payload.get("role")

    # 管理员可以查看所有资产的解析进度，普通用户只能查看自己的
    query_user_id = user_id if user_role != 0 else None

    result = AssetService.get_parsing_progress(db=db, user_id=query_user_id, asset_id=asset_id)
    return Response.success(data=result)


@router.post("/{asset_id}/retry-parsing", response_model=Response, summary="Retry asset parsing")
async def retry_parsing(
    asset_id: int = Path(..., description="Asset ID"),
    product_id: Optional[int] = Body(None, description="关联的产品ID，用于建立资产和产品的关联"),
    db: Session = Depends(get_db),
    current_user_payload: dict = Depends(get_current_user_payload),
):
    user_id = int(current_user_payload["sub"])
    user_role = current_user_payload.get("role")

    # 管理员可以重新解析所有资产，普通用户只能重新解析自己的
    query_user_id = user_id if user_role != 0 else None

    result = await AssetService.retry_parsing(db=db, user_id=query_user_id, asset_id=asset_id, product_id=product_id)
    return Response.success(data=result, message="Retry task started")


@router.delete("/{asset_id}", response_model=Response, summary="Delete asset")
def delete_asset(
    asset_id: int = Path(..., description="Asset ID"),
    db: Session = Depends(get_db),
    current_user_payload: dict = Depends(get_current_user_payload),
):
    user_id = int(current_user_payload["sub"])
    user_role = current_user_payload.get("role")

    # 管理员可以删除所有资产，普通用户只能删除自己的
    query_user_id = user_id if user_role != 0 else None

    AssetService.delete_asset(db=db, user_id=query_user_id, asset_id=asset_id)
    return Response.success(data=None, message="Deleted successfully")
