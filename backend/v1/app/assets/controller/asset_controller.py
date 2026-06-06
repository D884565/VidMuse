from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, Path, UploadFile
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.store.database.sync_database import get_db
from backend.v1.app.assets.service.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["Asset Management"])


@router.post("/text", response_model=Response, summary="Create text material")
def create_text_asset(
    title: Optional[str] = Body(None, description="Asset title"),
    content_text: str = Body(..., description="Text material content"),
    db: Session = Depends(get_db),
):
    result = AssetService.create_text_asset(db=db, title=title, content_text=content_text)
    return Response.success(data=result, message="Created successfully")


@router.put("/{asset_id}/text", response_model=Response, summary="Update text material")
def update_text_asset(
    asset_id: int = Path(..., description="Asset ID"),
    title: Optional[str] = Body(None, description="Asset title"),
    content_text: str = Body(..., description="Text material content"),
    db: Session = Depends(get_db),
):
    result = AssetService.update_text_asset(
        db=db,
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
):
    result = await AssetService.upload_user_asset(
        db=db,
        background_tasks=background_tasks,
        file=file,
        type=type,
        title=title,
        source_type=source_type,
        skip_analysis=skip_analysis,
    )
    return Response.success(data=result, message="Uploaded successfully")


@router.post("/upload/init", response_model=Response, summary="Init resumable image upload")
def init_resumable_upload(
    file_name: str = Body(...),
    file_size: int = Body(...),
    chunk_size: int = Body(...),
    file_hash: str = Body(...),
    db: Session = Depends(get_db),
):
    result = AssetService.init_resumable_upload(
        db=db,
        file_name=file_name,
        file_size=file_size,
        chunk_size=chunk_size,
        file_hash=file_hash,
    )
    return Response.success(data=result, message="Initialized successfully")


@router.put("/upload/chunk", response_model=Response, summary="Upload image chunk")
async def upload_image_chunk(
    session_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    result = await AssetService.upload_image_chunk(
        db=db,
        session_id=session_id,
        chunk_index=chunk_index,
        chunk=chunk,
    )
    return Response.success(data=result, message="Chunk uploaded successfully")


@router.get("/upload/status", response_model=Response, summary="Get resumable upload status")
def get_upload_status(
    session_id: str,
    db: Session = Depends(get_db),
):
    result = AssetService.get_upload_status(db=db, session_id=session_id)
    return Response.success(data=result)


@router.post("/upload/complete", response_model=Response, summary="Complete resumable image upload")
def complete_resumable_upload(
    session_id: str = Body(...),
    title: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    result = AssetService.complete_resumable_upload(db=db, session_id=session_id, title=title)
    return Response.success(data=result, message="Upload completed")


@router.post("/upload/internal", response_model=Response, summary="Upload internal asset")
async def upload_internal_asset(
    file: UploadFile = File(..., description="File to upload"),
    type: int = Form(..., description="Asset type: 1-image, 2-video, 3-audio"),
    title: Optional[str] = Form(None, description="Asset title"),
    source_type: Optional[int] = Form(1, description="Source type"),
    skip_ai_analysis: Optional[bool] = Form(True, description="Skip AI analysis"),
    db: Session = Depends(get_db),
):
    result = await AssetService.upload_internal_asset(
        db=db,
        file=file,
        type=type,
        title=title,
        source_type=source_type,
        skip_ai_analysis=skip_ai_analysis,
    )
    return Response.success(data=result, message="Internal asset uploaded successfully")


@router.post("/{asset_id}/reupload", response_model=Response, summary="Directly reupload image asset")
async def reupload_image_asset(
    asset_id: int = Path(..., description="Asset ID"),
    file: UploadFile = File(..., description="Image file to replace the current asset"),
    title: Optional[str] = Form(None, description="Asset title"),
    db: Session = Depends(get_db),
):
    result = await AssetService.reupload_image_asset(
        db=db,
        asset_id=asset_id,
        file=file,
        title=title,
    )
    return Response.success(data=result, message="Reuploaded successfully")


@router.post("/{asset_id}/reupload/init", response_model=Response, summary="Init image reupload")
def init_image_reupload(
    asset_id: int = Path(..., description="Asset ID"),
    file_name: str = Body(...),
    file_size: int = Body(...),
    chunk_size: int = Body(...),
    file_hash: str = Body(...),
    db: Session = Depends(get_db),
):
    result = AssetService.init_image_reupload(
        db=db,
        asset_id=asset_id,
        file_name=file_name,
        file_size=file_size,
        chunk_size=chunk_size,
        file_hash=file_hash,
    )
    return Response.success(data=result, message="Reupload initialized successfully")


@router.post("/{asset_id}/reupload/complete", response_model=Response, summary="Complete image reupload")
def complete_image_reupload(
    asset_id: int = Path(..., description="Asset ID"),
    session_id: str = Body(...),
    title: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    result = AssetService.complete_image_reupload(
        db=db,
        asset_id=asset_id,
        session_id=session_id,
        title=title,
    )
    return Response.success(data=result, message="Reupload completed")


@router.get("", response_model=Response, summary="List assets")
def list_assets(
    type: Optional[int] = None,
    source_type: Optional[int] = None,
    keyword: Optional[str] = None,
    format: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    result = AssetService.list_assets(
        db=db,
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
):
    result = AssetService.get_asset_detail(db=db, asset_id=asset_id)
    return Response.success(data=result)


@router.put("/{asset_id}", response_model=Response, summary="Update asset")
def update_asset(
    asset_id: int = Path(..., description="Asset ID"),
    title: Optional[str] = Body(None, description="Asset title"),
    ai_features: Optional[dict] = Body(None, description="AI feature payload"),
    db: Session = Depends(get_db),
):
    result = AssetService.update_asset(
        db=db,
        asset_id=asset_id,
        title=title,
        ai_features=ai_features,
    )
    return Response.success(data=result, message="Updated successfully")


@router.post("/{asset_id}/parse", response_model=Response, summary="Parse asset")
async def parse_asset(
    asset_id: int = Path(..., description="Asset ID"),
    force: bool = Body(False, description="Force re-parse"),
    db: Session = Depends(get_db),
):
    result = await AssetService.parse_asset(db=db, asset_id=asset_id, force=force)
    return Response.success(data=result, message="Parse task started")


@router.get("/{asset_id}/parsing-progress", response_model=Response, summary="Get parsing progress")
def get_parsing_progress(
    asset_id: int = Path(..., description="Asset ID"),
    db: Session = Depends(get_db),
):
    result = AssetService.get_parsing_progress(db=db, asset_id=asset_id)
    return Response.success(data=result)


@router.post("/{asset_id}/retry-parsing", response_model=Response, summary="Retry asset parsing")
async def retry_parsing(
    asset_id: int = Path(..., description="Asset ID"),
    db: Session = Depends(get_db),
):
    result = await AssetService.retry_parsing(db=db, asset_id=asset_id)
    return Response.success(data=result, message="Retry task started")


@router.delete("/{asset_id}", response_model=Response, summary="Delete asset")
def delete_asset(
    asset_id: int = Path(..., description="Asset ID"),
    db: Session = Depends(get_db),
):
    AssetService.delete_asset(db=db, asset_id=asset_id)
    return Response.success(data=None, message="Deleted successfully")
