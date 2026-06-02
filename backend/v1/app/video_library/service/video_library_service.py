"""视频素材库业务逻辑层"""
from typing import List, Dict, Any, Optional, Tuple
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.v1.app.video_library.dao.video_library_dao import VideoLibraryDAO
from backend.v1.app.pipeline.processors.cluster.hot_report_fetch_processor import HotReportFetchProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.store.obj.factory import get_storage_client
from backend.framework.exceptions.error_codes import SYSTEM_ERROR, PARAM_ERROR
import logging
import uuid
import os

logger = logging.getLogger(__name__)


class VideoLibraryService:
    """视频素材库业务逻辑类"""

    def __init__(self):
        self.obj_store = get_storage_client()
        self.hot_report_fetcher = HotReportFetchProcessor()

    @staticmethod
    async def get_video_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        category: Optional[str] = None,
        min_hot_score: Optional[int] = None,
        source_type: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取视频列表"""
        videos, total = await VideoLibraryDAO.list(
            db, page, page_size, category, min_hot_score, source_type, keyword
        )
        return [video.to_dict() for video in videos], total

    @staticmethod
    async def get_video_detail(db: AsyncSession, video_id: int) -> Optional[Dict[str, Any]]:
        """获取视频详情"""
        video = await VideoLibraryDAO.get_by_id(db, video_id)
        return video.to_dict() if video else None

    async def upload_video(
        self,
        db: AsyncSession,
        file: UploadFile,
        created_by: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """上传视频文件"""
        # 生成文件名
        ext = os.path.splitext(file.filename)[1].lower()
        file_name = f"video-library/{uuid.uuid4().hex}{ext}"

        try:
            # 上传到对象存储
            content = await file.read()
            url = await self.obj_store.put_object(file_name, content, file.content_type)

            # 创建视频记录
            video = await VideoLibraryDAO.create(
                db,
                title=title or file.filename,
                description=description,
                url=url,
                file_size=len(content),
                format=ext.lstrip("."),
                source_type=0,  # 内部上传
                category=category,
                tags=tags,
                created_by=created_by,
                parsing_status="pending"
            )

            # TODO: 触发解析流水线（复用现有assets模块的解析逻辑）
            # execution_id = await self._trigger_parsing_pipeline(video)
            # await VideoLibraryDAO.update(db, video.id, execution_id=execution_id)

            return video.to_dict()

        except Exception as e:
            logger.error(f"上传视频失败: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=SYSTEM_ERROR[0],
                detail=f"上传视频失败: {str(e)}"
            )

    @staticmethod
    async def create_video(
        db: AsyncSession,
        created_by: int,
        **kwargs
    ) -> Dict[str, Any]:
        """手动创建视频记录"""
        # 检查URL是否已存在
        if "url" in kwargs:
            existing = await VideoLibraryDAO.get_by_url(db, kwargs["url"])
            if existing:
                raise HTTPException(
                    status_code=PARAM_ERROR[0],
                    detail="该视频URL已存在"
                )

        video = await VideoLibraryDAO.create(
            db,
            created_by=created_by,
            source_type=2,  # 人工录入
            **kwargs
        )
        return video.to_dict()

    @staticmethod
    async def update_video(
        db: AsyncSession,
        video_id: int,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """更新视频信息"""
        video = await VideoLibraryDAO.update(db, video_id, **kwargs)
        return video.to_dict() if video else None

    @staticmethod
    async def delete_video(db: AsyncSession, video_id: int) -> bool:
        """删除视频"""
        return await VideoLibraryDAO.delete(db, video_id)

    async def batch_import_hot_reports(
        self,
        db: AsyncSession,
        created_by: int,
        category: Optional[str] = None,
        min_hot_score: int = 80,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, int]:
        """批量导入爆款视频"""
        # 构建上下文参数
        context_data = {
            "min_hot_score": min_hot_score
        }
        if category:
            context_data["category"] = category
        if start_time:
            context_data["start_time"] = start_time
        if end_time:
            context_data["end_time"] = end_time
        if limit:
            context_data["limit"] = limit

        context = PipelineContext(data=context_data)

        # 调用HotReportFetchProcessor拉取数据
        try:
            context = self.hot_report_fetcher.process(context)
            reports = context.get("HOT_REPORT_LIST", [])
            embeddings = context.get("REPORT_EMBEDDINGS", [])

            if not reports:
                return {"success": 0, "duplicate": 0, "failed": 0}

        except Exception as e:
            logger.error(f"拉取爆款报告失败: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=SYSTEM_ERROR[0],
                detail=f"拉取爆款报告失败: {str(e)}"
            )

        # 处理导入
        success_count = 0
        duplicate_count = 0
        failed_count = 0

        for report in reports:
            try:
                # 检查是否已存在
                existing = await VideoLibraryDAO.get_by_url(db, report["video_url"])
                if existing:
                    duplicate_count += 1
                    continue

                # 构建数据
                video_data = {
                    "title": report.get("title"),
                    "description": report.get("description"),
                    "url": report["video_url"],
                    "cover_url": report.get("cover_url"),
                    "duration": report.get("duration"),
                    "hot_score": report.get("hot_score"),
                    "category": report.get("category") or category,
                    "tags": report.get("tags"),
                    "parsed_data": report,
                    "source_type": 1,  # 爆款抓取
                    "created_by": created_by,
                    "parsing_status": "completed"  # 已有解析数据
                }

                await VideoLibraryDAO.create(db, **video_data)
                success_count += 1

            except Exception as e:
                logger.error(f"导入视频失败: {str(e)}, 报告数据: {report}")
                failed_count += 1
                continue

        return {
            "success": success_count,
            "duplicate": duplicate_count,
            "failed": failed_count
        }

    @staticmethod
    async def trigger_parsing(db: AsyncSession, video_id: int) -> bool:
        """手动触发视频解析"""
        video = await VideoLibraryDAO.get_by_id(db, video_id)
        if not video:
            return False

        # 更新状态为pending
        await VideoLibraryDAO.update_parsing_status(db, video_id, "pending")

        # TODO: 触发解析流水线
        # execution_id = await self._trigger_parsing_pipeline(video)
        # await VideoLibraryDAO.update(db, video_id, execution_id=execution_id)

        return True
