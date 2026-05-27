from typing import Optional
from sqlalchemy.orm import Session

from backend.v1.app.models.asset import Asset


class AssetDAO:
    """资产数据访问层"""

    @staticmethod
    def create_asset(db: Session, asset_data: dict) -> Asset:
        """创建资产记录"""
        asset = Asset(**asset_data)
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return

    @staticmethod
    def insert_batch_assets(db: Session, assets_data: list[dict]) -> None:
        """批量插入资产记录"""
        db.bulk_insert_mappings(Asset, assets_data)
        db.commit()


    @staticmethod
    def get_asset_by_id(db: Session, asset_id: int) -> Optional[Asset]:
        """根据ID获取资产"""
        return db.query(Asset).filter(Asset.id == asset_id).first()


    @staticmethod
    def update_asset(db: Session, asset_id: int, update_data: dict) -> Optional[Asset]:
        """更新资产信息"""
        db.query(Asset).filter(Asset.id == asset_id).update(update_data)
        db.commit()
        return AssetDAO.get_asset_by_id(db, asset_id)

    @staticmethod
    def delete_asset(db: Session, asset_id: int) -> bool:
        """删除资产"""
        result = db.query(Asset).filter(Asset.id == asset_id).delete()
        db.commit()
        return result > 0

    @staticmethod
    def list_assets(
            db: Session,
            user_id: Optional[int] = None,
            type: Optional[int] = None,
            source_type: Optional[int] = None,
            keyword: Optional[str] = None,
            format: Optional[str] = None,
            page: int = 1,
            page_size: int = 20
    ) -> tuple[int, list[Asset]]:
        """分页查询资产列表"""
        query = db.query(Asset)

        # 用户筛选
        if user_id is not None:
            query = query.filter(Asset.user_id == user_id)

        # 类型筛选
        if type is not None:
            query = query.filter(Asset.type == type)

        # 来源筛选
        if source_type is not None:
            query = query.filter(Asset.source_type == source_type)

        # 格式筛选
        if format:
            query = query.filter(Asset.format == format.lower())

        # 关键词搜索
        if keyword:
            title_match = Asset.title.like(f"%{keyword}%")
            query = query.filter(title_match)

        total = query.count()

        offset = (page - 1) * page_size
        assets = query.order_by(Asset.created_at.desc()).offset(offset).limit(page_size).all()

        return total, assets
