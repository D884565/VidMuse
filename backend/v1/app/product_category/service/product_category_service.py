"""商品分类业务逻辑层"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from backend.v1.app.product_category.dao.product_category_dao import ProductCategoryDAO
from backend.v1.app.product_category.dao.schema import CategoryCreateRequest, CategoryUpdateRequest, CategoryInfo, CategoryTree


class ProductCategoryService:
    """商品分类业务逻辑层"""

    @staticmethod
    def _build_category_tree(categories: List, parent_id: int = 0) -> List[CategoryTree]:
        """构建分类树

        :param categories: 全部分类列表
        :param parent_id: 父分类ID
        :return: 分类树
        """
        tree = []
        for category in categories:
            if category.parent_id == parent_id:
                # 转换为CategoryTree对象
                category_tree = CategoryTree(
                    id=category.id,
                    name=category.name,
                    parent_id=category.parent_id,
                    level=category.level,
                    path=category.path,
                    sort=category.sort,
                    created_at=category.created_at.isoformat() if category.created_at else "",
                    updated_at=category.updated_at.isoformat() if category.updated_at else ""
                )
                # 递归构建子树
                category_tree.children = ProductCategoryService._build_category_tree(categories, category.id)
                tree.append(category_tree)
        return tree

    @staticmethod
    def _generate_category_path(parent: Optional, category_id: int) -> str:
        """生成分类路径

        :param parent: 父分类对象
        :param category_id: 当前分类ID
        :return: 分类路径，如"/1/2/3/"
        """
        if parent is None:
            return f"/{category_id}/"
        return f"{parent.path}{category_id}/"

    @staticmethod
    def create_category(db: Session, request: CategoryCreateRequest) -> CategoryInfo:
        """创建分类

        :param db: 数据库会话
        :param request: 创建分类请求
        :return: 创建后的分类信息
        :raises ValueError: 父分类不存在、分类名称重复、层级超过三级
        """
        # 检查父分类是否存在
        parent = None
        if request.parent_id != 0:
            parent = ProductCategoryDAO.get_category_by_id(db, request.parent_id)
            if not parent:
                raise ValueError(f"父分类ID {request.parent_id} 不存在")

            # 检查层级，最多三级
            if parent.level >= 3:
                raise ValueError("最多支持三级分类，无法在三级分类下创建子分类")

        # 检查同一父分类下是否有重名
        existing = ProductCategoryDAO.get_category_by_name_and_parent(db, request.name, request.parent_id)
        if existing:
            raise ValueError(f"分类名称 '{request.name}' 已存在")

        # 准备分类数据
        category_data = request.model_dump()
        if parent:
            category_data["level"] = parent.level + 1
        else:
            category_data["level"] = 1

        # 先创建获取ID
        temp_category = ProductCategoryDAO.create_category(db, category_data)

        # 生成路径并更新
        path = ProductCategoryService._generate_category_path(parent, temp_category.id)
        category = ProductCategoryDAO.update_category(db, temp_category.id, {"path": path})

        return CategoryInfo(
            id=category.id,
            name=category.name,
            parent_id=category.parent_id,
            level=category.level,
            path=category.path,
            sort=category.sort,
            created_at=category.created_at.isoformat() if category.created_at else "",
            updated_at=category.updated_at.isoformat() if category.updated_at else ""
        )

    @staticmethod
    def update_category(db: Session, category_id: int, request: CategoryUpdateRequest) -> CategoryInfo:
        """更新分类

        :param db: 数据库会话
        :param category_id: 分类ID
        :param request: 更新分类请求
        :return: 更新后的分类信息
        :raises ValueError: 分类不存在、父分类不存在、分类名称重复、层级超过三级
        """
        # 检查分类是否存在
        category = ProductCategoryDAO.get_category_by_id(db, category_id, include_deleted=True)
        if not category:
            raise ValueError(f"分类ID {category_id} 不存在")

        update_data = request.model_dump(exclude_unset=True)
        if not update_data:
            raise ValueError("没有需要更新的字段")

        # 如果更新父分类
        if "parent_id" in update_data:
            new_parent_id = update_data["parent_id"]
            if new_parent_id == category.id:
                raise ValueError("父分类不能是自己")

            # 检查新父分类是否存在
            new_parent = None
            if new_parent_id != 0:
                new_parent = ProductCategoryDAO.get_category_by_id(db, new_parent_id)
                if not new_parent:
                    raise ValueError(f"父分类ID {new_parent_id} 不存在")

                # 检查层级，最多三级
                if new_parent.level >= 3:
                    raise ValueError("最多支持三级分类，无法将分类移动到三级分类下")

                # 检查是否是自己的子分类
                if new_parent.path.startswith(category.path):
                    raise ValueError("父分类不能是自己的子分类")

            # 检查同一父分类下是否有重名
            name_to_check = update_data.get("name", category.name)
            existing = ProductCategoryDAO.get_category_by_name_and_parent(db, name_to_check, new_parent_id)
            if existing and existing.id != category_id:
                raise ValueError(f"分类名称 '{name_to_check}' 已存在")

            # 计算新的层级
            if new_parent:
                new_level = new_parent.level + 1
            else:
                new_level = 1
            update_data["level"] = new_level

            # 生成新的路径
            new_path = ProductCategoryService._generate_category_path(new_parent, category_id)
            update_data["path"] = new_path

            # 更新所有子分类的路径
            children = ProductCategoryDAO.list_all_categories(db)
            for child in children:
                if child.path.startswith(category.path) and child.id != category_id:
                    child_new_path = child.path.replace(category.path, new_path, 1)
                    ProductCategoryDAO.update_category(db, child.id, {"path": child_new_path, "level": new_level + (child.level - category.level)})

        # 如果只更新名称，检查重名
        elif "name" in update_data:
            existing = ProductCategoryDAO.get_category_by_name_and_parent(db, update_data["name"], category.parent_id)
            if existing and existing.id != category_id:
                raise ValueError(f"分类名称 '{update_data['name']}' 已存在")

        # 更新分类
        updated_category = ProductCategoryDAO.update_category(db, category_id, update_data)

        return CategoryInfo(
            id=updated_category.id,
            name=updated_category.name,
            parent_id=updated_category.parent_id,
            level=updated_category.level,
            path=updated_category.path,
            sort=updated_category.sort,
            created_at=updated_category.created_at.isoformat() if updated_category.created_at else "",
            updated_at=updated_category.updated_at.isoformat() if updated_category.updated_at else ""
        )

    @staticmethod
    def delete_category(db: Session, category_id: int) -> bool:
        """删除分类（软删除）

        :param db: 数据库会话
        :param category_id: 分类ID
        :return: 是否删除成功
        :raises ValueError: 分类不存在、分类下有子分类、分类下有商品
        """
        # 检查分类是否存在
        category = ProductCategoryDAO.get_category_by_id(db, category_id)
        if not category:
            raise ValueError(f"分类ID {category_id} 不存在")

        # 检查是否有子分类
        if ProductCategoryDAO.has_children(db, category_id):
            raise ValueError("该分类下有子分类，请先删除子分类")

        # 检查是否有商品关联该分类
        from backend.v1.app.product.dao.product_dao import ProductDAO
        # 这里简单判断，实际应该查询是否有商品关联该分类
        # TODO: 实现查询商品是否关联该分类的逻辑

        return ProductCategoryDAO.delete_category(db, category_id)

    @staticmethod
    def get_category_info(db: Session, category_id: int) -> Optional[CategoryInfo]:
        """获取分类详情

        :param db: 数据库会话
        :param category_id: 分类ID
        :return: 分类信息，不存在返回 None
        """
        category = ProductCategoryDAO.get_category_by_id(db, category_id)
        if not category:
            return None

        return CategoryInfo(
            id=category.id,
            name=category.name,
            parent_id=category.parent_id,
            level=category.level,
            path=category.path,
            sort=category.sort,
            created_at=category.created_at.isoformat() if category.created_at else "",
            updated_at=category.updated_at.isoformat() if category.updated_at else ""
        )

    @staticmethod
    def get_category_tree(db: Session) -> List[CategoryTree]:
        """获取分类树

        :param db: 数据库会话
        :return: 分类树
        """
        all_categories = ProductCategoryDAO.list_all_categories(db)
        return ProductCategoryService._build_category_tree(all_categories)

    @staticmethod
    def get_categories_by_level(db: Session, level: int) -> List[CategoryInfo]:
        """按层级查询分类列表

        :param db: 数据库会话
        :param level: 分类层级（1/2/3）
        :return: 分类列表
        :raises ValueError: 层级参数错误
        """
        if level not in [1, 2, 3]:
            raise ValueError("层级参数错误，只能是1、2、3")

        categories = ProductCategoryDAO.list_categories_by_level(db, level)
        return [
            CategoryInfo(
                id=c.id,
                name=c.name,
                parent_id=c.parent_id,
                level=c.level,
                path=c.path,
                sort=c.sort,
                created_at=c.created_at.isoformat() if c.created_at else "",
                updated_at=c.updated_at.isoformat() if c.updated_at else ""
            ) for c in categories
        ]
