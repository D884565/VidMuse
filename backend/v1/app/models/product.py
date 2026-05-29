"""商品模型"""
import datetime
from sqlalchemy import BigInteger, String, Integer, Text, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class Product(Base):
    """商品表 ORM 模型"""
    __tablename__ = "products"

    # 主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 外键：关联用户，NULL 表示平台公共商品
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建者ID，NULL=平台公共")

    # 基本信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称")
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="品牌")
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="分类（冗余存储三级分类名称）")
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True, comment="关联分类ID，对应product_categories.id")
    category_path: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="分类路径，冗余存储方便检索，如\"/1/2/3/\"")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="商品描述")

    # 卖点、规格、标签：以 JSON 字符串存储
    selling_points: Mapped[str | None] = mapped_column(Text, nullable=True, comment="卖点JSON数组")
    specs: Mapped[str | None] = mapped_column(Text, nullable=True, comment="规格JSON对象")
    tags: Mapped[str | None] = mapped_column(Text, nullable=True, comment="标签JSON数组")

    # 价格与图片
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, comment="价格（元，保留2位小数）")
    main_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="主图URL")

    # 来源平台信息
    detail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="商品详情页链接")
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="来源平台 taobao/jd/pdd/douyin 等")
    platform_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="平台商品ID")

    # 时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系：商品属于某个用户
    user = relationship("User", back_populates="products")

    # 关系：商品属于某个分类
    category_obj = relationship("ProductCategory", back_populates="products")
