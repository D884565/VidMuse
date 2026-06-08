"""商品数据访问层

职责：封装所有对 products 表的数据库操作，Service 层通过此层访问数据库。
卖点(selling_points) 字段在数据库中以 JSON 字符串存储，
写入时自动序列化，读取时由 Schema 层的 product_to_dict() 负责反序列化。
"""
import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.v1.app.models.product import Product


class ProductDAO:
    """商品数据访问层"""

    @staticmethod
    def create_product(db: Session, product_data: dict) -> Product:
        """创建商品记录

        :param db: 数据库会话
        :param product_data: 商品字段字典
        :return: 创建后的 Product 对象
        """
        # 将 list/dict 类型的字段序列化为 JSON 字符串后存储
        for field in ("selling_points", "images"):
            if isinstance(product_data.get(field), (list, dict)):
                product_data[field] = json.dumps(product_data[field], ensure_ascii=False)
        product = Product(**product_data)
        db.add(product)
        db.flush()
        db.refresh(product)
        return product

    @staticmethod
    def get_product_by_id(db: Session, product_id: int, include_category: bool = False, include_assets: bool = False) -> Optional[Product]:
        """根据商品ID查询商品

        :param db: 数据库会话
        :param product_id: 商品ID
        :param include_category: 是否预加载关联的分类信息
        :param include_assets: 是否预加载关联的资产信息
        :return: Product 对象，不存在返回 None
        """
        query = db.query(Product)
        if include_category:
            from sqlalchemy.orm import joinedload
            query = query.options(joinedload(Product.category_obj))
        if include_assets:
            from sqlalchemy.orm import joinedload
            query = query.options(joinedload(Product.assets))
        return query.filter(Product.id == product_id).first()

    @staticmethod
    def update_product(db: Session, product_id: int, update_data: dict) -> Product:
        """更新商品信息

        :param db: 数据库会话
        :param product_id: 商品ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 Product 对象
        """
        # 同样处理 list/dict 字段的序列化
        for field in ("selling_points",):
            if isinstance(update_data.get(field), (list, dict)):
                update_data[field] = json.dumps(update_data[field], ensure_ascii=False)
        db.query(Product).filter(Product.id == product_id).update(update_data)
        db.flush()
        return ProductDAO.get_product_by_id(db, product_id)

    @staticmethod
    def delete_product(db: Session, product_id: int) -> bool:
        """删除商品

        :param db: 数据库会话
        :param product_id: 商品ID
        :return: 是否删除成功
        """
        result = db.query(Product).filter(Product.id == product_id).delete()
        db.flush()
        return result > 0

    @staticmethod
    def list_products(
        db: Session,
        user_id: Optional[int] = None,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        category1: Optional[int] = None,
        category2: Optional[int] = None,
        category3: Optional[int] = None,
        platform: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        only_public: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[int, list[Product]]:
        """分页查询商品列表

        默认返回当前用户的商品 + 平台公共商品（user_id IS NULL）。
        支持按关键词、分类、平台、价格区间筛选。

        :param db: 数据库会话
        :param user_id: 当前用户ID（用于筛选自己的商品 + 公共商品）
        :param keyword: 按名称/品牌/描述模糊搜索
        :param category: 按分类名称筛选（兼容旧版）
        :param category1: 按一级分类ID筛选
        :param category2: 按二级分类ID筛选
        :param category3: 按三级分类ID筛选（等效于category_id）
        :param platform: 按来源平台筛选
        :param min_price: 最低价格
        :param max_price: 最高价格
        :param only_public: 是否只看公共商品（user_id IS NULL）
        :param page: 页码
        :param page_size: 每页数量
        :return: (总数量, 商品列表)
        """
        query = db.query(Product)

        # 筛选：自己的商品 + 平台公共商品（user_id 为 NULL）
        if user_id is not None:
            if only_public:
                query = query.filter(Product.user_id.is_(None))
            else:
                query = query.filter(or_(Product.user_id == user_id, Product.user_id.is_(None)))

        # 关键词搜索：名称、品牌、描述
        if keyword:
            query = query.filter(
                or_(
                    Product.name.like(f"%{keyword}%"),
                    Product.brand.like(f"%{keyword}%"),
                    Product.description.like(f"%{keyword}%"),
                )
            )
        if category:
            query = query.filter(Product.category == category)
        if category1:
            # 一级分类：路径以"/{category1}/"开头
            query = query.filter(Product.category_path.like(f"/{category1}/%"))
        if category2:
            # 二级分类：路径包含"/{category2}/"且是二级
            query = query.filter(Product.category_path.like(f"%/{category2}/%"))
        if category3:
            # 三级分类：直接匹配category_id
            query = query.filter(Product.category_id == category3)
        if platform:
            query = query.filter(Product.platform == platform)
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)

        total = query.count()
        offset = (page - 1) * page_size
        products = query.order_by(Product.created_at.desc()).offset(offset).limit(page_size).all()

        return total, products
