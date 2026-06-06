"""商品资产关联数据访问层"""
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.v1.app.models.product_asset import ProductAsset
from backend.v1.app.models.asset import Asset


class ProductAssetDAO:
    """商品资产关联数据访问层"""

    @staticmethod
    def create_product_asset(db: Session, product_id: int, asset_id: int, role: str = "image") -> ProductAsset:
        """创建商品资产关联
        :param db: 数据库会话
        :param product_id: 商品ID
        :param asset_id: 资产ID
        :param role: 资产角色
        :return: 创建后的ProductAsset对象
        """
        product_asset = ProductAsset(
            product_id=product_id,
            asset_id=asset_id,
            role=role
        )
        db.add(product_asset)
        db.commit()
        db.refresh(product_asset)
        return product_asset

    @staticmethod
    def create_product_assets_batch(db: Session, product_id: int, asset_ids: List[int],
                                   roles: Optional[dict[int, str]] = None) -> List[ProductAsset]:
        """批量创建商品资产关联
        :param db: 数据库会话
        :param product_id: 商品ID
        :param asset_ids: 资产ID列表
        :param roles: 资产角色字典，key为asset_id，value为角色
        :return: 创建后的ProductAsset对象列表
        """
        roles = roles or {}
        product_assets = []
        for asset_id in asset_ids:
            role = roles.get(asset_id, "image")
            product_asset = ProductAsset(
                product_id=product_id,
                asset_id=asset_id,
                role=role
            )
            product_assets.append(product_asset)
            db.add(product_asset)
        db.commit()
        for pa in product_assets:
            db.refresh(pa)
        return product_assets

    @staticmethod
    def get_assets_by_product_id(db: Session, product_id: int) -> List[Asset]:
        """根据商品ID查询关联的所有资产
        :param db: 数据库会话
        :param product_id: 商品ID
        :return: 资产对象列表
        """
        return db.query(Asset).join(ProductAsset).filter(ProductAsset.product_id == product_id).all()

    @staticmethod
    def get_assets_by_product_id_and_role(db: Session, product_id: int, role: str) -> List[Asset]:
        """根据商品ID和角色查询关联的资产
        :param db: 数据库会话
        :param product_id: 商品ID
        :param role: 资产角色
        :return: 资产对象列表
        """
        return db.query(Asset).join(ProductAsset).filter(
            ProductAsset.product_id == product_id,
            ProductAsset.role == role
        ).all()

    @staticmethod
    def delete_product_asset(db: Session, product_id: int, asset_id: int, role: Optional[str] = None) -> bool:
        """删除商品资产关联
        :param db: 数据库会话
        :param product_id: 商品ID
        :param asset_id: 资产ID
        :param role: 资产角色（可选，若指定则只删除对应角色的关联）
        :return: 是否删除成功
        """
        query = db.query(ProductAsset).filter(
            ProductAsset.product_id == product_id,
            ProductAsset.asset_id == asset_id
        )
        if role is not None:
            query = query.filter(ProductAsset.role == role)
        result = query.delete()
        db.commit()
        return result > 0

    @staticmethod
    def delete_all_by_product_id(db: Session, product_id: int) -> bool:
        """删除商品的所有资产关联
        :param db: 数据库会话
        :param product_id: 商品ID
        :return: 是否删除成功
        """
        result = db.query(ProductAsset).filter(ProductAsset.product_id == product_id).delete()
        db.commit()
        return result > 0
