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
