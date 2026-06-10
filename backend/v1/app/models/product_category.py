"""商品分类模型"""
import datetime
from sqlalchemy import BigInteger, String, Integer, SmallInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class ProductCategory(Base):
    """商品分类表 ORM 模型"""
    __tablename__ = "product_categories"

    # 主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="分类ID")

    # 基本信息
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="分类名称")
    parent_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="父分类ID，0表示一级分类")
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="分类层级：1-一级分类，2-二级分类，3-三级分类")
    path: Mapped[str] = mapped_column(String(200), nullable=False, comment="分类路径，如\"/1/2/3/\"，方便查询子树")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序权重，数值越大越靠前")
    is_deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="是否删除：0-未删除，1-已删除")

    # 时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系：分类下的商品
    products = relationship("Product", back_populates="category_obj")
