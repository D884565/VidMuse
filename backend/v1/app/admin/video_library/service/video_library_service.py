"""视频素材库业务逻辑层"""
from typing import List, Dict, Any, Optional, Tuple
from fastapi import UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.framework.exceptions import BusinessException
from backend.v1.app.admin.video_library.dao.video_library_dao import VideoLibraryDAO
from backend.v1.app.product.dao.product_category_dao import ProductCategoryDAO
from backend.v1.app.pipeline.processors.cluster.hot_report_fetch_processor import HotReportFetchProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.framework.exceptions.error_codes import SYSTEM_ERROR, PARAM_ERROR
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.assets.service.asset_service import AssetService
from backend.v1.app.slice.dao.slice_dao import SliceDAO
from backend.store.database.sync_database import get_db as get_sync_db
import logging
from backend.store.vector.factory import get_vector_db_client

logger = logging.getLogger(__name__)


class VideoLibraryService:
    """视频素材库业务逻辑类"""

    def __init__(self):
        self.obj_store = get_vector_db_client("video")
        self.hot_report_fetcher = HotReportFetchProcessor()

    @staticmethod
    async def get_video_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        category: Optional[str] = None,
        category_id: Optional[int] = None,
        min_hot_score: Optional[int] = None,
        source_type: Optional[int] = None,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取视频列表"""
        videos, total = await VideoLibraryDAO.list(
            db, page, page_size, category, category_id, min_hot_score, source_type, keyword, status
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
        category_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
        trigger_ai_parse: bool = True,
    ) -> Dict[str, Any]:
        """上传视频文件"""
        try:
            # 1. 复用AssetService的内部上传逻辑，统一处理文件验证、存储、资产创建
            sync_db = next(get_sync_db())

            # 检测文件类型（虽然应该是视频，但复用统一逻辑）
            asset_type = AssetService.detect_asset_type(file)
            if asset_type != 2:  # 确保是视频类型
                raise BusinessException(PARAM_ERROR, "只能上传视频文件")

            # 上传内部资产，跳过自动解析，后面统一处理
            asset_dict = await AssetService.upload_internal_asset(
                db=sync_db,
                file=file,
                type=asset_type,
                title=title or file.filename,
                source_type=0,  # 内部上传
                skip_ai_analysis=True  # 跳过自动解析，由视频库自己控制解析流程
            )

            # 2. 处理分类关联
            video_data = {
                "title": asset_dict["title"],
                "description": description,
                "url": asset_dict["url"],
                "file_size": asset_dict["file_size"],
                "format": asset_dict["format"],
                "source_type": 0,  # 内部上传
                "category": category,
                "tags": tags,
                "created_by": created_by,
                "asset_id": asset_dict["id"],
                "parsing_status": "pending"
            }

            if category_id is not None:
                category_obj = ProductCategoryDAO.get_category_by_id(sync_db, category_id)
                if not category_obj:
                    raise BusinessException(PARAM_ERROR, f"分类ID {category_id} 不存在")
                if category_obj.level != 3:
                    raise BusinessException(PARAM_ERROR, "只能选择三级分类关联视频")
                # 自动填充分类信息
                video_data["category_id"] = category_id
                video_data["category"] = category_obj.name
                video_data["category_path"] = category_obj.path

            # 3. 创建视频库记录，关联资产ID
            video = await VideoLibraryDAO.create(
                db,
                **video_data
            )

            # 4. 更新资产表的解析状态为pending
            AssetDAO.update_asset(sync_db, asset_dict["id"], {
                "parsing_status": "pending"
            })

            # 5. 根据trigger_ai_parse参数决定是否触发AI解析
            if trigger_ai_parse:
                # 复用AssetsService的解析逻辑，保持与资产模块完全统一
                await AssetService._extract_ai_features(
                    id=asset_dict["id"],
                    asset_type=2,  # 视频类型
                    asset_url=asset_dict["url"],
                    db=sync_db
                )

                # 同步资产表的最新状态到视频库表
                updated_asset = AssetDAO.get_asset_by_id(sync_db, asset_dict["id"])
                await VideoLibraryDAO.update(db, video.id, {
                    "execution_id": updated_asset.execution_id,
                    "parsing_status": updated_asset.parsing_status,
                    "parsing_error": updated_asset.parsing_error
                })
            else:
                # 不触发AI解析，保持pending状态，用户可后续手动触发
                logger.info(f"视频 {video.id} 上传完成，已跳过AI解析")

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

        # 处理分类关联
        create_data = kwargs.copy()
        category_id = create_data.pop("category_id", None)
        if category_id is not None:
            # 获取同步数据库会话
            sync_db = next(get_sync_db())
            category_obj = ProductCategoryDAO.get_category_by_id(sync_db, category_id)
            if not category_obj:
                raise BusinessException(PARAM_ERROR, f"分类ID {category_id} 不存在")
            if category_obj.level != 3:
                raise BusinessException(PARAM_ERROR, "只能选择三级分类关联视频")
            # 自动填充分类信息
            create_data["category_id"] = category_id
            create_data["category"] = category_obj.name
            create_data["category_path"] = category_obj.path

        video = await VideoLibraryDAO.create(
            db,
            created_by=created_by,
            source_type=2,  # 人工录入
            **create_data
        )
        return video.to_dict()

    @staticmethod
    async def update_video(
        db: AsyncSession,
        video_id: int,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """更新视频信息"""
        update_data = kwargs.copy()
        category_id = update_data.pop("category_id", None)

        # 处理分类关联
        if category_id is not None:
            # 获取同步数据库会话
            sync_db = next(get_sync_db())
            category_obj = ProductCategoryDAO.get_category_by_id(sync_db, category_id)
            if not category_obj:
                raise BusinessException(PARAM_ERROR, f"分类ID {category_id} 不存在")
            if category_obj.level != 3:
                raise BusinessException(PARAM_ERROR, "只能选择三级分类关联视频")
            # 自动填充分类信息
            update_data["category_id"] = category_id
            update_data["category"] = category_obj.name
            update_data["category_path"] = category_obj.path
        elif "category_id" in kwargs and category_id is None:
            # 清空分类关联
            update_data["category_id"] = None
            update_data["category"] = None
            update_data["category_path"] = None

        video = await VideoLibraryDAO.update(db, video_id, **update_data)
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
        category_id: Optional[int] = None,
        min_hot_score: int = 80,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, int]:
        """批量导入爆款视频"""
        # 处理分类关联
        category_obj = None
        if category_id is not None:
            # 获取同步数据库会话
            sync_db = next(get_sync_db())
            category_obj = ProductCategoryDAO.get_category_by_id(sync_db, category_id)
            if not category_obj:
                raise BusinessException(PARAM_ERROR, f"分类ID {category_id} 不存在")
            if category_obj.level != 3:
                raise BusinessException(PARAM_ERROR, "只能选择三级分类关联视频")

        # 构建上下文参数
        context_data = {
            "min_hot_score": min_hot_score
        }
        if category:
            context_data["category"] = category
        elif category_obj:
            context_data["category"] = category_obj.name
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

                # 如果指定了分类ID，统一使用关联的分类信息
                if category_obj:
                    video_data["category_id"] = category_id
                    video_data["category"] = category_obj.name
                    video_data["category_path"] = category_obj.path

                # 创建对应的内部资产（如果需要关联slice的话）
                # TODO: 这里可以选择是否为导入的爆款视频创建asset记录
                # 如果需要slice关联，可以直接调用AssetDAO创建资产并触发pipeline解析
                # sync_db = next(get_sync_db())
                # asset = AssetDAO.create_asset(sync_db, asset_data)
                # video_data["asset_id"] = asset.id
                # 然后触发VideoParsingPipeline进行解析

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

            # 获取资产信息
            asset = AssetDAO.get_asset_by_id(sync_db, video.asset_id)
            if not asset:
                return False

            # 复用AssetsService的解析逻辑，保持与资产模块完全统一
            if not force and asset.parsing_status == "failed" and asset.execution_id:
                # 失败的任务尝试重试（支持断点恢复）
                await AssetService.retry_parsing(
                    db=sync_db,
                    asset_id=video.asset_id
                )
            else:
                # 正常触发解析
                await AssetService.parse_asset(
                    db=sync_db,
                    asset_id=video.asset_id,
                    force=force
                )

            # 同步资产表的最新状态到视频库表
            updated_asset = AssetDAO.get_asset_by_id(sync_db, video.asset_id)
            await VideoLibraryDAO.update(db, video_id, {
                "execution_id": updated_asset.execution_id,
                "parsing_status": updated_asset.parsing_status,
                "parsing_error": updated_asset.parsing_error
            })

            return True

        except Exception as e:
            logger.error(f"触发视频解析失败: {str(e)}", exc_info=True)
            return False

    @staticmethod
    async def get_parsing_progress(db: AsyncSession, video_id: int) -> Optional[Dict[str, Any]]:
        """查询视频解析进度"""
        video = await VideoLibraryDAO.get_by_id(db, video_id)
        if not video or not video.asset_id:
            return None

        try:
            # 获取同步数据库会话
            sync_db = next(get_sync_db())

            # 复用AssetsService的进度查询逻辑
            progress = AssetService.get_parsing_progress(
                db=sync_db,
                asset_id=video.asset_id
            )

            # 添加视频ID到返回结果
            progress["video_id"] = video_id
            return progress

        except Exception as e:
            logger.error(f"查询视频解析进度失败: {str(e)}", exc_info=True)
            return None
