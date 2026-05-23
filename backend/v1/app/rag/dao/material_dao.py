from typing import Optional
from sqlalchemy.orm import Session

from backend.v1.app.models.material import Material


class MaterialDAO:
    """素材数据访问层"""

    @staticmethod
    def create_material(db: Session, material_data: dict) -> Material:
        """创建素材记录"""
        material = Material(**material_data)
        db.add(material)
        db.commit()
        db.refresh(material)
        return material

    @staticmethod
    def get_material_by_id(db: Session, material_id: int) -> Material:
        """根据ID获取素材"""
        return db.query(Material).filter(Material.id == material_id).first()

    @staticmethod
    def update_material(db: Session, material_id: int, update_data: dict) -> Material:
        """更新素材信息"""
        db.query(Material).filter(Material.id == material_id).update(update_data)
        db.commit()
        return MaterialDAO.get_material_by_id(db, material_id)

    @staticmethod
    def delete_material(db: Session, material_id: int) -> bool:
        """删除素材"""
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
        """分页查询素材列表"""
        query = db.query(Material)

        if material_type is not None:
            query = query.filter(Material.type == material_type)

        if keyword:
            title_match = Material.title.like(f"%{keyword}%")
            query = query.filter(title_match)

        total = query.count()

        offset = (page - 1) * page_size
        materials = query.order_by(Material.created_at.desc()).offset(offset).limit(page_size).all()

        return total, materials
