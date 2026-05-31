"""切片控制器"""
from typing import Optional
from fastapi import APIRouter, Depends, Path, Body
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.store.database.sync_database import get_db
from backend.v1.app.slice.service.slice_service import SliceService

router = APIRouter(prefix="", tags=["切片管理"])


@router.get("/slices/{slice_id}", response_model=Response, summary="获取切片详情")
def get_slice_detail(
        slice_id: int = Path(..., description="切片ID"),
        db: Session = Depends(get_db)
):
    """获取单个切片的详细信息"""
    result = SliceService.get_slice_detail(db=db, slice_id=slice_id)
    return Response.success(data=result)


@router.get("/assets/{asset_id}/slices", response_model=Response, summary="获取资产的所有切片")
def get_asset_slices(
        asset_id: int = Path(..., description="资产ID"),
        db: Session = Depends(get_db)
):
    """获取指定视频资产的所有切片列表"""
    result = SliceService.get_asset_slices(db=db, asset_id=asset_id)
    return Response.success(data=result)


@router.put("/slices/{slice_id}", response_model=Response, summary="更新切片信息")
def update_slice(
        slice_id: int = Path(..., description="切片ID"),
        title: Optional[str] = Body(None, description="切片标题"),
        ai_features: Optional[dict] = Body(None, description="AI特征因子"),
        start_time: Optional[int] = Body(None, description="开始时间(毫秒)"),
        end_time: Optional[int] = Body(None, description="结束时间(毫秒)"),
        duration: Optional[int] = Body(None, description="时长(毫秒)"),
        db: Session = Depends(get_db)
):
    """更新切片信息"""
    update_data = {}
    if title is not None:
        update_data["title"] = title
    if ai_features is not None:
        update_data["ai_features"] = ai_features
    if start_time is not None:
        update_data["start_time"] = start_time
    if end_time is not None:
        update_data["end_time"] = end_time
    if duration is not None:
        update_data["duration"] = duration

    result = SliceService.update_slice(db=db, slice_id=slice_id, update_data=update_data)
    return Response.success(data=result, message="更新成功")


@router.delete("/slices/{slice_id}", response_model=Response, summary="删除切片")
def delete_slice(
        slice_id: int = Path(..., description="切片ID"),
        db: Session = Depends(get_db)
):
    """删除单个切片"""
    SliceService.delete_slice(db=db, slice_id=slice_id)
    return Response.success(data=None, message="删除成功")
