"""视频素材库业务逻辑层"""
from typing import List, Dict, Any, Optional, Tuple
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.framework.exceptions import BusinessException
from backend.v1.app.video_library.dao.video_library_dao import VideoLibraryDAO
from backend.v1.app.pipeline.processors.cluster.hot_report_fetch_processor import HotReportFetchProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.store.obj.factory import get_storage_client
from backend.framework.exceptions.error_codes import SYSTEM_ERROR, PARAM_ERROR
from backend.v1.app.assets.service.asset_service import AssetService
from backend.v1.app.slice.dao.slice_dao import SliceDAO
from backend.store.database.sync_database import get_db as get_sync_db
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
        try:
            # 获取同步数据库会话用于调用AssetService
            sync_db = next(get_sync_db())

            # 调用内部资产上传接口，直接复用现有逻辑
            asset_dict = await AssetService.upload_internal_asset(
                db=sync_db,
                file=file,
                type=2,  # 视频类型
                title=title or file.filename,
                source_type=0,  # 内部上传
                skip_ai_analysis=False  # 不跳过AI分析，自动触发解析
            )

            # 创建视频库记录，关联资产ID
            video = await VideoLibraryDAO.create(
                db,
                title=asset_dict["title"],
                description=description,
                url=asset_dict["url"],
                cover_url=asset_dict.get("cover_url"),
                file_size=asset_dict["file_size"],
                duration=asset_dict.get("duration"),
                format=asset_dict["format"],
                source_type=0,  # 内部上传
                category=category,
                tags=tags,
                created_by=created_by,
                asset_id=asset_dict["id"],
                parsing_status=asset_dict["parsing_status"],
                execution_id=asset_dict.get("execution_id")
            )

            # 更新asset的parsing_status到video_library
            if asset_dict.get("parsing_status") == "completed":
                # 如果已经解析完成，获取解析数据
                # TODO: 可以选择将解析数据同步到parsed_data字段
                pass

            return video.to_dict()

        except Exception as e:
            logger.error(f"上传视频失败: {str(e)}", exc_info=True)
            raise BusinessException(SYSTEM_ERROR, f"上传视频失败: {str(e)}")

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

                # 创建对应的内部资产（如果需要关联slice的话）
                # TODO: 这里可以选择是否为导入的爆款视频创建asset记录
                # 如果需要slice关联，可以调用AssetService创建资产并解析
                # sync_db = next(get_sync_db())
                # asset_dict = await AssetService.create_external_asset(...)
                # video_data["asset_id"] = asset_dict["id"]

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
    async def get_video_slices(db: AsyncSession, video_id: int) -> List[Dict[str, Any]]:
        """获取视频对应的切片列表"""
        video = await VideoLibraryDAO.get_by_id(db, video_id)
        if not video or not video.asset_id:
            return []

        try:
            # 获取同步数据库会话
            sync_db = next(get_sync_db())

            # 查询该资产对应的所有切片
            slices = SliceDAO.get_slices_by_asset_id(sync_db, video.asset_id)

            # 转换为字典格式
            return [s.to_dict() for s in slices]

        except Exception as e:
            logger.error(f"查询视频切片失败: {str(e)}", exc_info=True)
            return []

    @staticmethod
    async def trigger_parsing(db: AsyncSession, video_id: int, force: bool = False) -> bool:
        """手动触发视频解析"""
        video = await VideoLibraryDAO.get_by_id(db, video_id)
        if not video or not video.asset_id:
            return False

        try:
            # 获取同步数据库会话
            sync_db = next(get_sync_db())

            # 调用AssetService的触发解析接口
            result = await AssetService.trigger_parsing(
                db=sync_db,
                asset_id=video.asset_id,
                force=force
            )

            # 更新video_library的解析状态和execution_id
            update_data = {
                "parsing_status": result.get("parsing_status", "pending")
            }
            if result.get("execution_id"):
                update_data["execution_id"] = result["execution_id"]

            await VideoLibraryDAO.update(db, video_id, **update_data)

            return True

        except Exception as e:
            logger.error(f"触发视频解析失败: {str(e)}", exc_info=True)
            return False
