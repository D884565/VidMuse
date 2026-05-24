from typing import Optional
from sqlalchemy.orm import Session

from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import PARAM_ERROR
from backend.v1.app.rag.dao.project_dao import ProjectDAO


class ProjectService:
    """项目业务逻辑层"""

    # 状态映射：数据库字符串状态 -> 接口整数状态
    STATUS_TO_INT = {
        "draft": 0,
        "script_ready": 0,  # 脚本准备好也归为待生成
        "processing": 1,
        "completed": 2,
        "failed": 3
    }

    # 状态名称映射
    STATUS_NAME = {
        0: "待生成",
        1: "生成中",
        2: "已完成",
        3: "失败"
    }

    @staticmethod
    def _convert_project_to_response(project) -> dict:
        """将数据库项目对象转换为接口响应格式"""
        project_dict = project.__dict__
        # 移除sqlalchemy内部属性
        project_dict.pop("_sa_instance_state", None)

        # 转换状态
        status_str = project_dict.pop("status", "draft")
        status_int = ProjectService.STATUS_TO_INT.get(status_str, 0)
        project_dict["status"] = status_int
        project_dict["status_name"] = ProjectService.STATUS_NAME.get(status_int, "未知")

        # 补充默认字段
        if not project_dict.get("user_id"):
            project_dict["user_id"] = 10001  # 暂时固定用户ID，待用户系统实现后替换

        return project_dict

    @staticmethod
    def create_project(
            db: Session,
            title: str,
            description: Optional[str] = None,
            product_url: Optional[str] = None,
            product_id: Optional[int] = None
    ) -> dict:
        """创建新项目"""
        # 参数校验
        if not title or len(title.strip()) == 0:
            raise BusinessException(PARAM_ERROR, "项目标题不能为空")
        if len(title) > 200:
            raise BusinessException(PARAM_ERROR, "项目标题不能超过200字符")
        if product_url and len(product_url) > 1000:
            raise BusinessException(PARAM_ERROR, "商品链接不能超过1000字符")

        # 准备数据
        project_data = {
            "title": title.strip(),
            "description": description.strip() if description else None,
            "product_url": product_url.strip() if product_url else None,
            "product_id": product_id,
            "user_id": 10001,  # 暂时固定用户ID，待用户系统实现后替换
            "status": "draft"
        }

        # 创建项目
        project = ProjectDAO.create_project(db, project_data)

        # 转换为响应格式
        result = ProjectService._convert_project_to_response(project)

        # 只返回需要的字段
        return {
            "id": result["id"],
            "title": result["title"],
            "description": result["description"],
            "product_url": result["product_url"],
            "video_output_url": result["video_output_url"],
            "user_id": result["user_id"],
            "product_id": result["product_id"],
            "status": result["status"],
            "status_name": result["status_name"],
            "created_at": result["created_at"].isoformat() + "Z",
            "updated_at": result["updated_at"].isoformat() + "Z"
        }

    @staticmethod
    def list_projects(
            db: Session,
            status: Optional[int] = None,
            keyword: Optional[str] = None,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            page: int = 1,
            page_size: int = 20
    ) -> dict:
        """查询项目列表"""
        # 参数校验
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        if status is not None and status not in [0, 1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的状态值")

        # 查询数据
        total, projects = ProjectDAO.list_projects(
            db=db,
            status=status,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size
        )

        # 转换为响应格式
        project_list = []
        for project in projects:
            project_dict = ProjectService._convert_project_to_response(project)
            # 列表页需要的字段
            list_item = {
                "id": project_dict["id"],
                "title": project_dict["title"],
                "description": project_dict["description"],
                "product_url": project_dict["product_url"],
                "video_output_url": project_dict["video_output_url"],
                "user_id": project_dict["user_id"],
                "product_id": project_dict["product_id"],
                "status": project_dict["status"],
                "status_name": project_dict["status_name"],
                "frame_count": 0,  # 暂时为0，待帧管理实现后替换
                "total_duration": 0,  # 暂时为0，待时长计算实现后替换
                "created_at": project_dict["created_at"].isoformat() + "Z",
                "updated_at": project_dict["updated_at"].isoformat() + "Z"
            }
            project_list.append(list_item)

        return {
            "list": project_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
            }
        }

    @staticmethod
    def get_project_detail(db: Session, project_id: int) -> dict:
        """获取项目详情"""
        project = ProjectDAO.get_project_by_id(db, project_id)
        if not project:
            raise BusinessException(PARAM_ERROR, "项目不存在")

        project_dict = ProjectService._convert_project_to_response(project)

        # 详情页需要的字段
        detail = {
            "id": project_dict["id"],
            "title": project_dict["title"],
            "description": project_dict["description"],
            "product_url": project_dict["product_url"],
            "video_output_url": project_dict["video_output_url"],
            "user_id": project_dict["user_id"],
            "product_id": project_dict["product_id"],
            "status": project_dict["status"],
            "status_name": project_dict["status_name"],
            "frames": [],  # 暂时为空，待帧管理实现后替换
            "created_at": project_dict["created_at"].isoformat() + "Z",
            "updated_at": project_dict["updated_at"].isoformat() + "Z"
        }

        return detail

    @staticmethod
    def update_project(
            db: Session,
            project_id: int,
            title: Optional[str] = None,
            description: Optional[str] = None,
            product_url: Optional[str] = None,
            product_id: Optional[int] = None
    ) -> dict:
        """更新项目信息"""
        # 检查项目是否存在
        project = ProjectDAO.get_project_by_id(db, project_id)
        if not project:
            raise BusinessException(PARAM_ERROR, "项目不存在")

        # 准备更新数据
        update_data = {}

        if title is not None:
            title = title.strip()
            if len(title) == 0:
                raise BusinessException(PARAM_ERROR, "项目标题不能为空")
            if len(title) > 200:
                raise BusinessException(PARAM_ERROR, "项目标题不能超过200字符")
            update_data["title"] = title

        if description is not None:
            update_data["description"] = description.strip() if description else None

        if product_url is not None:
            product_url = product_url.strip()
            if len(product_url) > 1000:
                raise BusinessException(PARAM_ERROR, "商品链接不能超过1000字符")
            update_data["product_url"] = product_url

        if product_id is not None:
            update_data["product_id"] = product_id

        # 如果没有要更新的字段，直接返回
        if not update_data:
            project_dict = ProjectService._convert_project_to_response(project)
            return {
                "id": project_dict["id"],
                "title": project_dict["title"],
                "updated_at": project_dict["updated_at"].isoformat() + "Z"
            }

        # 执行更新
        updated_project = ProjectDAO.update_project(db, project_id, update_data)
        project_dict = ProjectService._convert_project_to_response(updated_project)

        return {
            "id": project_dict["id"],
            "title": project_dict["title"],
            "updated_at": project_dict["updated_at"].isoformat() + "Z"
        }

    @staticmethod
    def delete_project(db: Session, project_id: int) -> None:
        """删除项目"""
        # 检查项目是否存在
        project = ProjectDAO.get_project_by_id(db, project_id)
        if not project:
            raise BusinessException(PARAM_ERROR, "项目不存在")

        # 执行删除
        success = ProjectDAO.delete_project(db, project_id)
        if not success:
            raise BusinessException(PARAM_ERROR, "删除失败")
