"""商品分类数据访问层

职责：封装所有对 product_categories 表的数据库操作，Service 层通过此层访问数据库。
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.v1.app.models.product_category import ProductCategory


class ProductCategoryDAO:
    """商品分类数据访问层"""

    @staticmethod
    def create_category(db: Session, category_data: dict) -> ProductCategory:
        """创建分类记录

        :param db: 数据库会话
        :param category_data: 分类字段字典
        :return: 创建后的 ProductCategory 对象
        """
        category = ProductCategory(**category_data)
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    @staticmethod
    def get_category_by_id(db: Session, category_id: int, include_deleted: bool = False) -> Optional[ProductCategory]:
        """根据分类ID查询分类

        :param db: 数据库会话
        :param category_id: 分类ID
        :param include_deleted: 是否包含已删除的分类
        :return: ProductCategory 对象，不存在返回 None
        """
        query = db.query(ProductCategory).filter(ProductCategory.id == category_id)
        if not include_deleted:
            query = query.filter(ProductCategory.is_deleted == 0)
        return query.first()

    @staticmethod
    def get_category_by_name_and_parent(db: Session, name: str, parent_id: int, include_deleted: bool = False) -> Optional[ProductCategory]:
        """根据分类名称和父ID查询分类（用于重名检查）

        :param db: 数据库会话
        :param name: 分类名称
        :param parent_id: 父分类ID
        :param include_deleted: 是否包含已删除的分类
        :return: ProductCategory 对象，不存在返回 None
        """
        query = db.query(ProductCategory).filter(
            ProductCategory.name == name,
            ProductCategory.parent_id == parent_id
        )
        if not include_deleted:
            query = query.filter(ProductCategory.is_deleted == 0)
        return query.first()

    @staticmethod
    def update_category(db: Session, category_id: int, update_data: dict) -> Optional[ProductCategory]:
        """更新分类信息

        :param db: 数据库会话
        :param category_id: 分类ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 ProductCategory 对象，不存在返回 None
        """
        db.query(ProductCategory).filter(ProductCategory.id == category_id).update(update_data)
        db.commit()
        return ProductCategoryDAO.get_category_by_id(db, category_id, include_deleted=True)

    @staticmethod
    def delete_category(db: Session, category_id: int) -> bool:
        """删除分类（软删除）

        :param db: 数据库会话
        :param category_id: 分类ID
        :return: 是否删除成功
        """
        result = db.query(ProductCategory).filter(
            ProductCategory.id == category_id,
            ProductCategory.is_deleted == 0
        ).update({"is_deleted": 1})
        db.commit()
        return result > 0

    @staticmethod
    def list_categories_by_level(db: Session, level: int, include_deleted: bool = False) -> List[ProductCategory]:
        """按层级查询分类列表

        :param db: 数据库会话
        :param level: 分类层级
        :param include_deleted: 是否包含已删除的分类
        :return: 分类列表
        """
        query = db.query(ProductCategory).filter(ProductCategory.level == level)
        if not include_deleted:
            query = query.filter(ProductCategory.is_deleted == 0)
        return query.order_by(ProductCategory.sort.desc(), ProductCategory.id.asc()).all()

    @staticmethod
    def list_categories_by_parent_id(db: Session, parent_id: int, include_deleted: bool = False) -> List[ProductCategory]:
        """按父ID查询子分类列表

        :param db: 数据库会话
        :param parent_id: 父分类ID
        :param include_deleted: 是否包含已删除的分类
        :return: 子分类列表
        """
        query = db.query(ProductCategory).filter(ProductCategory.parent_id == parent_id)
        if not include_deleted:
            query = query.filter(ProductCategory.is_deleted == 0)
        return query.order_by(ProductCategory.sort.desc(), ProductCategory.id.asc()).all()

    @staticmethod
    def list_all_categories(db: Session, include_deleted: bool = False) -> List[ProductCategory]:
        """查询所有分类

        :param db: 数据库会话
        :param include_deleted: 是否包含已删除的分类
        :return: 全部分类列表
        """
        query = db.query(ProductCategory)
        if not include_deleted:
            query = query.filter(ProductCategory.is_deleted == 0)
        return query.order_by(ProductCategory.level.asc(), ProductCategory.sort.desc(), ProductCategory.id.asc()).all()

    @staticmethod
    def has_children(db: Session, category_id: int, include_deleted: bool = False) -> bool:
        """判断分类是否有子分类

        :param db: 数据库会话
        :param category_id: 分类ID
        :param include_deleted: 是否包含已删除的子分类
        :return: 是否有子分类
        """
        query = db.query(ProductCategory).filter(ProductCategory.parent_id == category_id)
        if not include_deleted:
            query = query.filter(ProductCategory.is_deleted == 0)
        return query.first() is not None
