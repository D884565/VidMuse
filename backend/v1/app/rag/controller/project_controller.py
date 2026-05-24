from typing import Optional
from fastapi import APIRouter, Depends, Body, Path
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.store.database.sync_database import get_db
from backend.v1.app.rag.service.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["项目管理"])


@router.post("", response_model=Response, summary="创建项目")
def create_project(
        title: str = Body(..., description="项目标题", max_length=200),
        description: Optional[str] = Body(None, description="项目描述"),
        product_url: Optional[str] = Body(None, description="商品链接", max_length=1000),
        product_id: Optional[int] = Body(None, description="关联的商品ID"),
        db: Session = Depends(get_db)
):
    """创建一个新的AIGC视频项目"""
    result = ProjectService.create_project(
        db=db,
        title=title,
        description=description,
        product_url=product_url,
        product_id=product_id
    )
    return Response.success(data=result, message="项目创建成功")


@router.get("", response_model=Response, summary="获取项目列表")
def list_projects(
        status: Optional[int] = None,
        keyword: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
):
    """获取当前用户的项目列表"""
    result = ProjectService.list_projects(
        db=db,
        status=status,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size
    )
    return Response.success(data=result)


@router.get("/{project_id}", response_model=Response, summary="获取项目详情")
def get_project_detail(
        project_id: int = Path(..., description="项目ID"),
        db: Session = Depends(get_db)
):
    """获取指定项目的详细信息"""
    result = ProjectService.get_project_detail(db=db, project_id=project_id)
    return Response.success(data=result)


@router.put("/{project_id}", response_model=Response, summary="更新项目")
def update_project(
        project_id: int = Path(..., description="项目ID"),
        title: Optional[str] = Body(None, description="项目标题", max_length=200),
        description: Optional[str] = Body(None, description="项目描述"),
        product_url: Optional[str] = Body(None, description="商品链接", max_length=1000),
        product_id: Optional[int] = Body(None, description="商品ID"),
        db: Session = Depends(get_db)
):
    """更新项目信息"""
    result = ProjectService.update_project(
        db=db,
        project_id=project_id,
        title=title,
        description=description,
        product_url=product_url,
        product_id=product_id
    )
    return Response.success(data=result, message="项目更新成功")


@router.delete("/{project_id}", response_model=Response, summary="删除项目")
def delete_project(
        project_id: int = Path(..., description="项目ID"),
        db: Session = Depends(get_db)
):
    """删除指定项目（级联删除关联的帧数据）"""
    ProjectService.delete_project(db=db, project_id=project_id)
    return Response.success(data=None, message="项目删除成功")
