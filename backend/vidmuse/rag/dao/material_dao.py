from typing import Optional, cast
from sqlalchemy.orm import Session

from backend.vidmuse.rag.model.material import Material


class MaterialDAO:
    """素材数据访问层"""

    @staticmethod
    def create_material(db: Session, material_data: dict) -> Material:
        """
        创建素材记录
        :param db: 数据库会话
        :param material_data: 素材数据
        :return: 创建的素材对象
        """
        material = Material(**material_data)
        db.add(material)
        db.commit()
        db.refresh(material)
        return material

    @staticmethod
    def get_material_by_id(db: Session, material_id: int) -> Material:
        """
        根据ID获取素材
        :param db: 数据库会话
        :param material_id: 素材ID
        :return: 素材对象
        """
        return db.query(Material).filter(Material.id == material_id).first()

    @staticmethod
    def update_material(db: Session, material_id: int, update_data: dict) -> Material:
        """
        更新素材信息
        :param db: 数据库会话
        :param material_id: 素材ID
        :param update_data: 更新数据
        :return: 更新后的素材对象
        """
        db.query(Material).filter(Material.id == material_id).update(update_data)
        db.commit()
        return MaterialDAO.get_material_by_id(db, material_id)

    @staticmethod
    def delete_material(db: Session, material_id: int) -> bool:
        """
        删除素材
        :param db: 数据库会话
        :param material_id: 素材ID
        :return: 是否删除成功
        """
        result = db.query(Material).filter(Material.id == material_id).delete()
        db.commit()
        return result > 0

    @staticmethod
    def list_materials(
            db: Session,
            material_type: Optional[int] = None,
            keyword: Optional[str] = None,
            uploader_id: Optional[int] = None,
            page: int = 1,
            page_size: int = 20
    ) -> tuple[int, list[Material]]:
        """
        分页查询素材列表
        :param db: 数据库会话
        :param material_type: 素材类型筛选
        :param keyword: 标题/标签关键词搜索
        :param uploader_id: 上传者ID筛选（暂未实现，预留字段）
        :param page: 页码，从1开始
        :param page_size: 每页数量
        :return: 总条数，素材列表
        """
        query = db.query(Material)

        # 素材类型筛选
        if material_type is not None:
            query = query.filter(Material.type == material_type)

        # 关键词搜索：匹配标题或AI特征中的标签
        if keyword:
            # 匹配标题
            title_match = Material.title.like(f"%{keyword}%")
            # 匹配AI特征中的标签（JSON字段包含关键词）
            query = query.filter(title_match)

        # 上传者筛选（预留字段，当前表中无uploader_id，暂不实现）
        # if uploader_id is not None:
        #     query = query.filter(Material.uploader_id == uploader_id)

        # 计算总数
        total = query.count()

        # 分页
        offset = (page - 1) * page_size
        materials = query.order_by(Material.created_at.desc()).offset(offset).limit(page_size).all()

        return total, materials