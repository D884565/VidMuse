"""商品模块 Pydantic 模型

定义商品模块的请求体和响应体结构，以及 ORM 对象到字典的转换工具。
卖点、规格、标签在数据库中存储为 JSON 字符串，这里负责序列化/反序列化。
"""
import json
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field


# ==================== 请求模型 ====================

class ProductCreateRequest(BaseModel):
    """创建商品请求体"""
    name: str = Field(..., min_length=1, max_length=200, description="商品名称")
    brand: Optional[str] = Field(None, max_length=100, description="品牌")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    description: Optional[str] = Field(None, description="商品描述")
    selling_points: Optional[List[str]] = Field(None, description="卖点列表，如['SPF50+高倍防晒', '防水防汗']")
    price: Optional[Decimal] = Field(None, description="价格（元，保留2位小数）")
    main_image_url: Optional[str] = Field(None, max_length=500, description="主图URL")
    detail_url: Optional[str] = Field(None, max_length=1000, description="商品详情页链接")
    platform: Optional[str] = Field(None, max_length=20, description="来源平台 taobao/jd/pdd/douyin")
    platform_id: Optional[str] = Field(None, max_length=100, description="平台商品ID")
    specs: Optional[Dict[str, Any]] = Field(None, description="规格参数，如{'容量': '60ml', '产地': '日本'}")
    tags: Optional[List[str]] = Field(None, description="标签列表，如['防晒', '夏季必备']")


class ProductUpdateRequest(BaseModel):
    """更新商品请求体（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="商品名称")
    brand: Optional[str] = Field(None, max_length=100, description="品牌")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    description: Optional[str] = Field(None, description="商品描述")
    selling_points: Optional[List[str]] = Field(None, description="卖点列表")
    price: Optional[Decimal] = Field(None, description="价格")
    main_image_url: Optional[str] = Field(None, max_length=500, description="主图URL")
    detail_url: Optional[str] = Field(None, max_length=1000, description="详情页链接")
    platform: Optional[str] = Field(None, max_length=20, description="来源平台")
    platform_id: Optional[str] = Field(None, max_length=100, description="平台商品ID")
    specs: Optional[Dict[str, Any]] = Field(None, description="规格参数")
    tags: Optional[List[str]] = Field(None, description="标签列表")


# ==================== 工具函数 ====================

def _parse_json_field(value, default=None):
    """将 JSON 字符串解析为 Python 对象

    数据库中 selling_points/specs/tags 存储为 JSON 字符串，
    读取后需要反序列化为 list/dict 供前端使用。

    :param value: JSON 字符串或已解析的对象
    :param default: 解析失败时的默认值
    :return: 解析后的 Python 对象
    """
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default
    return value


def product_to_dict(product) -> dict:
    """将 Product ORM 对象转换为字典

    负责将数据库中的 JSON 字符串字段反序列化为 Python 对象，
    并格式化时间字段为 ISO 8601 字符串。

    :param product: Product ORM 对象
    :return: 商品信息字典，可直接作为 API 响应
    """
    return {
        "id": product.id,
        "user_id": product.user_id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "description": product.description,
        "selling_points": _parse_json_field(product.selling_points, []),
        "price": float(product.price) if product.price is not None else None,
        "main_image_url": product.main_image_url,
        "detail_url": product.detail_url,
        "platform": product.platform,
        "platform_id": product.platform_id,
        "specs": _parse_json_field(product.specs, {}),
        "tags": _parse_json_field(product.tags, []),
        "is_public": product.user_id is None,  # user_id 为空表示平台公共商品
        "created_at": product.created_at.isoformat() if product.created_at else "",
        "updated_at": product.updated_at.isoformat() if product.updated_at else "",
    }
