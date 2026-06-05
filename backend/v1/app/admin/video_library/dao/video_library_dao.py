"""视频素材库数据访问层"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from backend.v1.app.admin.video_library.model.video_library import VideoLibrary
import logging

logger = logging.getLogger(__name__)


class VideoLibraryDAO:
    """视频素材库数据访问类"""

    @staticmethod
    async def create(db: AsyncSession, **kwargs) -> VideoLibrary:
        """创建视频记录"""
        video = VideoLibrary(**kwargs)
        db.add(video)
        await db.commit()
        await db.refresh(video)
        return video

    @staticmethod
    async def get_by_id(db: AsyncSession, video_id: int) -> Optional[VideoLibrary]:
        """根据ID查询视频"""
        result = await db.execute(select(VideoLibrary).where(VideoLibrary.id == video_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_url(db: AsyncSession, url: str) -> Optional[VideoLibrary]:
        """根据URL查询视频（去重用）"""
        result = await db.execute(select(VideoLibrary).where(VideoLibrary.url == url))
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        category: Optional[str] = None,
        category_id: Optional[int] = None,
        min_hot_score: Optional[int] = None,
        source_type: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> tuple[List[VideoLibrary], int]:
        """分页查询视频列表"""
        query = select(VideoLibrary)

        # 条件过滤
        if category:
            query = query.where(VideoLibrary.category == category)
        if category_id is not None:
            query = query.where(VideoLibrary.category_id == category_id)
        if min_hot_score is not None:
            query = query.where(VideoLibrary.hot_score >= min_hot_score)
        if source_type is not None:
            query = query.where(VideoLibrary.source_type == source_type)
        if keyword:
            query = query.where(
                (VideoLibrary.title.like(f"%{keyword}%")) |
                (VideoLibrary.description.like(f"%{keyword}%"))
            )

        # 排序
        query = query.order_by(VideoLibrary.created_at.desc())

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        videos = result.scalars().all()

        # 查询总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        return videos, total

    @staticmethod
    async def update(db: AsyncSession, video_id: int, **kwargs) -> Optional[VideoLibrary]:
        """更新视频信息"""
        video = await VideoLibraryDAO.get_by_id(db, video_id)
        if not video:
            return None

        for key, value in kwargs.items():
            setattr(video, key, value)

        await db.commit()
        await db.refresh(video)
        return video

    @staticmethod
    async def delete(db: AsyncSession, video_id: int) -> bool:
        """删除视频"""
        result = await db.execute(delete(VideoLibrary).where(VideoLibrary.id == video_id))
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def batch_create(db: AsyncSession, video_list: List[Dict[str, Any]]) -> int:
        """批量创建视频记录"""
        videos = [VideoLibrary(**data) for data in video_list]
        db.add_all(videos)
        await db.commit()
        return len(videos)

    @staticmethod
    async def update_parsing_status(
        db: AsyncSession,
        video_id: int,
        status: str,
        parsed_data: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> Optional[VideoLibrary]:
        """更新解析状态"""
        update_data = {"parsing_status": status}
        if parsed_data:
            update_data["parsed_data"] = parsed_data
        if error:
            update_data["parsing_error"] = error

        return await VideoLibraryDAO.update(db, video_id, **update_data)
