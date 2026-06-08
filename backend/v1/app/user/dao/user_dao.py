"""用户数据访问层

职责：封装所有对 users 表的数据库操作，Service 层通过此层访问数据库。
"""
from typing import Optional
from sqlalchemy.orm import Session

from backend.v1.app.models.user import User


class UserDAO:
    """用户数据访问层"""

    @staticmethod
    def create_user(db: Session, user_data: dict) -> User:
        """创建用户记录

        :param db: 数据库会话
        :param user_data: 用户字段字典（username, password_hash, avatar_url, role, status）
        :return: 创建后的 User 对象（含自动生成的 id、created_at 等）
        """
        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """根据用户ID查询用户

        :param db: 数据库会话
        :param user_id: 用户ID
        :return: User 对象，不存在返回 None
        """
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """根据用户名查询用户（用于登录、注册时查重）

        :param db: 数据库会话
        :param username: 用户名
        :return: User 对象，不存在返回 None
        """
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def update_user(db: Session, user_id: int, update_data: dict) -> User:
        """更新用户信息

        :param db: 数据库会话
        :param user_id: 用户ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 User 对象
        """
        db.query(User).filter(User.id == user_id).update(update_data)
        db.commit()
        return UserDAO.get_user_by_id(db, user_id)

    @staticmethod
    def list_users(
        db: Session,
        role: Optional[int] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[int, list[User]]:
        """分页查询用户列表

        :param db: 数据库会话
        :param role: 按角色筛选（可选）
        :param keyword: 按用户名模糊搜索（可选）
        :param page: 页码，从1开始
        :param page_size: 每页数量
        :return: (总数量, 用户列表)
        """
        query = db.query(User)

        # 按角色筛选
        if role is not None:
            query = query.filter(User.role == role)

        # 按用户名模糊搜索
        if keyword:
            query = query.filter(User.username.like(f"%{keyword}%"))

        total = query.count()

        offset = (page - 1) * page_size
        users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

        return total, users

    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        """删除用户（硬删除）

        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 删除成功返回True，用户不存在返回False
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        db.delete(user)
        db.commit()
        return True
