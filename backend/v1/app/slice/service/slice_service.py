"""切片业务逻辑层"""
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.v1.app.assets.dao import AssetDAO
from backend.v1.app.slice.dao.slice_dao import SliceDAO
<<<<<<< HEAD

=======
from backend.v1.app.assets.dao.asset_dao import AssetDAO
>>>>>>> ef2cd102a639b877b80fed22c991ce46b6da0f7b
from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import PARAM_ERROR


class SliceService:
    """切片业务逻辑层"""

    @staticmethod
    def get_slice_detail(db: Session, slice_id: int) -> dict:
        """获取切片详情"""
        slice_obj = SliceDAO.get_slice_by_id(db, slice_id)
        if not slice_obj:
            raise BusinessException(PARAM_ERROR, "切片不存在")
        return slice_obj.to_dict()

    @staticmethod
    def get_asset_slices(db: Session, asset_id: int) -> dict:
        """获取资产的所有切片"""
        # 检查资产是否存在
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "资产不存在")

        # 只有视频类型才有切片
        if asset.type != 2:
            raise BusinessException(PARAM_ERROR, "只有视频类型的资产才有切片")

        slices = SliceDAO.get_slices_by_asset_id(db, asset_id)
        slice_list = [s.to_dict() for s in slices]

        return {
            "asset_id": asset_id,
            "slices": slice_list,
            "total": len(slice_list)
        }

    @staticmethod
    def update_slice(db: Session, slice_id: int, update_data: dict) -> dict:
        """更新切片信息"""
        # 检查切片是否存在
        slice_obj = SliceDAO.get_slice_by_id(db, slice_id)
        if not slice_obj:
            raise BusinessException(PARAM_ERROR, "切片不存在")

        # 过滤允许更新的字段
        allowed_fields = ["title", "ai_features", "start_time", "end_time", "duration"]
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}

        if not filtered_data:
            return slice_obj.to_dict()

        updated_slice = SliceDAO.update_slice(db, slice_id, filtered_data)
        return updated_slice.to_dict()

    @staticmethod
    def delete_slice(db: Session, slice_id: int) -> None:
        """删除单个切片"""
        # 检查切片是否存在
        slice_obj = SliceDAO.get_slice_by_id(db, slice_id)
        if not slice_obj:
            raise BusinessException(PARAM_ERROR, "切片不存在")

        # 删除切片
        from sqlalchemy import delete
        from backend.v1.app.models.slice import Slice
        db.execute(delete(Slice).where(Slice.id == slice_id))
        db.commit()
