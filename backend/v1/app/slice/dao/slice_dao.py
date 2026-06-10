"""切片数据访问层"""
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.v1.app.models.slice import Slice


class SliceDAO:
    """切片数据访问层"""

    @staticmethod
    def create_slice(db: Session, slice_data: dict) -> Slice:
        """创建单个切片记录"""
        slice_obj = Slice(**slice_data)
        db.add(slice_obj)
        db.commit()
        db.refresh(slice_obj)
        return slice_obj

    @staticmethod
    def create_slices_batch(db: Session, slices_data: List[dict]) -> None:
        """批量创建切片记录"""
        db.bulk_insert_mappings(Slice, slices_data)
        db.commit()

    @staticmethod
    def get_slice_by_id(db: Session, slice_id: int) -> Optional[Slice]:
        """根据ID获取切片"""
        return db.query(Slice).filter(Slice.id == slice_id).first()

    @staticmethod
    def get_slices_by_asset_id(db: Session, asset_id: int) -> List[Slice]:
        """根据资产ID查询所有切片，按序号升序排列"""
        return db.query(Slice).filter(Slice.asset_id == asset_id).order_by(Slice.index.asc()).all()

    @staticmethod
    def delete_slices_by_asset_id(db: Session, asset_id: int) -> int:
        """删除某个资产的所有切片，返回删除的数量"""
        result = db.query(Slice).filter(Slice.asset_id == asset_id).delete()
        db.commit()
        return result

    @staticmethod
    def update_slice(db: Session, slice_id: int, update_data: dict) -> Optional[Slice]:
        """更新切片信息"""
        db.query(Slice).filter(Slice.id == slice_id).update(update_data)
        db.commit()
        return SliceDAO.get_slice_by_id(db, slice_id)
