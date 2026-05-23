from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.store.database.sync_database import get_db
from backend.v1.app.rag.service.material_service import MaterialService

router = APIRouter(prefix="/materials", tags=["素材管理"])


@router.post("", response_model=Response, summary="上传素材")
async def upload_material(
        file: UploadFile = File(..., description="素材文件"),
        type: int = Form(..., description="素材类型 1-图片 2-视频 3-音频"),
        title: str = Form(..., description="素材标题"),
        tags: Optional[str] = Form(None, description="标签，逗号分隔"),
        source_type: int = Form(1, description="来源 1-上传 2-AI生成 3-爬取 4-购买"),
        db: Session = Depends(get_db)
):
    """上传素材到素材库，支持图片/视频/音频"""
    material = await MaterialService.upload_material(
        db=db,
        file=file,
        material_type=type,
        title=title,
        tags=tags,
        source_type=source_type
    )
    return Response.success(data=material)


@router.get("", response_model=Response, summary="查询素材列表")
def list_materials(
        type: Optional[int] = None,
        keyword: Optional[str] = None,
        uploader_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
):
    """多维度检索素材列表"""
    result = MaterialService.list_materials(
        db=db,
        material_type=type,
        keyword=keyword,
        uploader_id=uploader_id,
        page=page,
        page_size=page_size
    )
    return Response.success(data=result)


@router.delete("/{material_id}", response_model=Response, summary="删除素材")
def delete_material(
        material_id: int,
        db: Session = Depends(get_db)
):
    """删除素材（仅上传者或管理员）"""
    current_user_id = None
    MaterialService.delete_material(
        db=db,
        material_id=material_id,
        current_user_id=current_user_id
    )
    return Response.success(data=None)
