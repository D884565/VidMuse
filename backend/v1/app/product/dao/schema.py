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
    category: Optional[str] = Field(None, max_length=100, description="分类（兼容旧版，传入category_id时会自动覆盖此字段）")
    category_id: Optional[int] = Field(None, description="关联分类ID，对应三级分类ID")
    description: Optional[str] = Field(None, description="商品描述")
    selling_points: Optional[List[str]] = Field(None, description="卖点列表，如['SPF50+高倍防晒', '防水防汗']")
    price: Optional[Decimal] = Field(None, description="价格（元，保留2位小数）")
    main_image_url: Optional[str] = Field(None, max_length=500, description="主图URL")
    detail_url: Optional[str] = Field(None, max_length=1000, description="商品详情页链接")
    platform: Optional[str] = Field(None, max_length=20, description="来源平台 taobao/jd/pdd/douyin")
    platform_id: Optional[str] = Field(None, max_length=100, description="平台商品ID")
    images: Optional[List[str]] = Field(None, description="商品图片URL列表（兼容旧版，推荐使用asset_ids关联已上传资产）")
    auto_parse: bool = Field(False, description="是否创建后自动触发解析")
    asset_ids: Optional[List[int]] = Field(None, description="关联的资产ID列表，可关联已上传的图片/视频/音频等")
    asset_roles: Optional[Dict[int, str]] = Field(None, description="资产角色映射，key为asset_id，value为角色（main/image/video/audio）")


class ProductUpdateRequest(BaseModel):
    """更新商品请求体（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="商品名称")
    brand: Optional[str] = Field(None, max_length=100, description="品牌")
    category: Optional[str] = Field(None, max_length=100, description="分类（兼容旧版，传入category_id时会自动覆盖此字段）")
    category_id: Optional[int] = Field(None, description="关联分类ID，对应三级分类ID")
    description: Optional[str] = Field(None, description="商品描述")
    selling_points: Optional[List[str]] = Field(None, description="卖点列表")
    price: Optional[Decimal] = Field(None, description="价格")
    main_image_url: Optional[str] = Field(None, max_length=500, description="主图URL")
    detail_url: Optional[str] = Field(None, max_length=1000, description="详情页链接")
    platform: Optional[str] = Field(None, max_length=20, description="来源平台")
    platform_id: Optional[str] = Field(None, max_length=100, description="平台商品ID")
    images: Optional[List[str]] = Field(None, description="商品图片URL列表")
    auto_parse: Optional[bool] = Field(None, description="是否自动触发解析")


# ==================== 工具函数 ====================

def _parse_json_field(value, default=None):
    """将 JSON 字符串解析为 Python 对象

    数据库中 selling_points 存储为 JSON 字符串，
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


def product_to_dict(product, include_category_info: bool = False, include_assets: bool = True) -> dict:
    """将 Product ORM 对象转换为字典

    负责将数据库中的 JSON 字符串字段反序列化为 Python 对象，
    并格式化时间字段为 ISO 8601 字符串。

    :param product: Product ORM 对象
    :param include_category_info: 是否包含完整的分类信息
    :param include_assets: 是否包含关联的资产信息
    :return: 商品信息字典，可直接作为 API 响应
    """
    result = {
        "id": product.id,
        "user_id": product.user_id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "category_id": product.category_id,
        "category_path": product.category_path,
        "description": product.description,
        "selling_points": _parse_json_field(product.selling_points, []),
        "price": float(product.price) if product.price is not None else None,
        "main_image_url": product.main_image_url,
        "images": _parse_json_field(product.images, []),
        "auto_parse": product.auto_parse,
        "detail_url": product.detail_url,
        "platform": product.platform,
        "platform_id": product.platform_id,
        "is_public": product.user_id is None,  # user_id 为空表示平台公共商品
        "parsing_status": getattr(product, "parsing_status", None),
        "execution_id": getattr(product, "execution_id", None),
        "parsing_error": getattr(product, "parsing_error", None),
        "ai_features": getattr(product, "ai_features", None),
        "created_at": product.created_at.isoformat() if product.created_at else "",
        "updated_at": product.updated_at.isoformat() if product.updated_at else "",
    }

    # 如果需要包含完整分类信息且有关联分类
    if include_category_info and product.category_obj:
        result["category_info"] = CategoryInfo(
            id=product.category_obj.id,
            name=product.category_obj.name,
            parent_id=product.category_obj.parent_id,
            level=product.category_obj.level,
            path=product.category_obj.path,
            sort=product.category_obj.sort,
            created_at=product.category_obj.created_at.isoformat() if product.category_obj.created_at else "",
            updated_at=product.category_obj.updated_at.isoformat() if product.category_obj.updated_at else ""
        ).model_dump() if hasattr(product, 'category_obj') and product.category_obj else None

    # 如果需要包含关联资产信息
    if include_assets and hasattr(product, 'assets') and product.assets:
        result["assets"] = []
        for asset in product.assets:
            # 获取资产角色（需要从中间表获取，这里简化处理，后续优化）
            asset_dict = asset.to_dict()
            result["assets"].append(asset_dict)

    return result



"""商品分类模块 Pydantic 模型"""
from typing import Optional, List
from pydantic import BaseModel, Field


# ==================== 请求模型 ====================

class CategoryCreateRequest(BaseModel):
    """创建分类请求体"""
    name: str = Field(..., min_length=1, max_length=100, description="分类名称")
    parent_id: Optional[int] = Field(0, description="父分类ID，0表示一级分类")
    sort: Optional[int] = Field(0, description="排序权重，数值越大越靠前")


class CategoryUpdateRequest(BaseModel):
    """更新分类请求体（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="分类名称")
    parent_id: Optional[int] = Field(None, description="父分类ID，0表示一级分类")
    sort: Optional[int] = Field(None, description="排序权重，数值越大越靠前")
    is_deleted: Optional[int] = Field(None, ge=0, le=1, description="是否删除：0-未删除，1-已删除")


# ==================== 响应模型 ====================

class CategoryInfo(BaseModel):
    """分类详情响应"""
    id: int = Field(..., description="分类ID")
    name: str = Field(..., description="分类名称")
    parent_id: int = Field(..., description="父分类ID")
    level: int = Field(..., description="分类层级：1-一级，2-二级，3-三级")
    path: str = Field(..., description="分类路径")
    sort: int = Field(..., description="排序权重")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")


class CategoryTree(CategoryInfo):
    """分类树节点"""
    children: List["CategoryTree"] = Field(default_factory=list, description="子分类列表")


# 解决循环引用
CategoryTree.model_rebuild()
