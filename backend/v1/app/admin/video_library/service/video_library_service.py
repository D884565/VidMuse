"""视频素材库业务逻辑层"""
import os
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from fastapi import UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.framework.exceptions import BusinessException
from backend.v1.app.admin.video_library.dao.video_library_dao import VideoLibraryDAO
from backend.v1.app.product.dao.product_category_dao import ProductCategoryDAO
from backend.v1.app.pipeline.processors.cluster.hot_report_fetch_processor import HotReportFetchProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
# BasePipeline 导入移到函数内部，避免循环导入
from backend.framework.exceptions.error_codes import SYSTEM_ERROR, PARAM_ERROR
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.slice.dao.slice_dao import SliceDAO
from backend.v1.app.pipeline.factory.pipeline_factory import PipelineFactory
from backend.store.database.sync_database import get_db as get_sync_db
from backend.store import get_storage_client
from backend.store.obj.local_client import get_local_storage_client
from backend.v1.app.config.config import settings
import logging
from backend.store.vector.factory import get_vector_db_client

logger = logging.getLogger(__name__)


class VideoLibraryService:
    """视频素材库业务逻辑类"""

    def __init__(self):
        self._obj_store = None
        self.hot_report_fetcher = HotReportFetchProcessor()
        self.video_exts = {"mp4", "avi", "mov", "flv", "wmv", "webm", "mkv"}

    @property
    def obj_store(self):
        if self._obj_store is None:
            self._obj_store = get_storage_client()
        return self._obj_store

    # ==================== 独立文件处理方法（不再依赖AssetService） ====================
    @staticmethod
    def detect_video_type(file: UploadFile) -> int:
        """检测上传文件是否为视频类型"""
        content_type = file.content_type or ""
        if content_type.startswith("video/"):
            return 2

        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext in VideoLibraryService().video_exts:
            return 2

        raise BusinessException(PARAM_ERROR, "只能上传视频文件，支持格式：mp4/avi/mov/flv/wmv/webm/mkv")

    @staticmethod
    def _validate_video_file(file: UploadFile) -> str:
        """验证视频文件合法性"""
        file_size = getattr(file, "size", None)
        if file_size is not None and file_size > settings.UPLOAD_MAX_SIZE:
            raise BusinessException(PARAM_ERROR, f"文件大小超过限制，最大支持 {settings.UPLOAD_MAX_SIZE // 1024 // 1024} MB")

        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        allowed_exts = settings.ALLOWED_EXTENSIONS.get(2, [])  # 2是视频类型
        if ext not in allowed_exts:
            raise BusinessException(PARAM_ERROR, f"不支持的文件格式：{ext}，支持格式：{', '.join(allowed_exts)}")
        return ext

    @staticmethod
    def generate_video_object_name(ext: str) -> str:
        """生成视频文件的存储路径"""
        type_dir = "video"
        uuid_str = str(uuid.uuid4()).replace("-", "")
        root = "materials"  # 视频库素材使用materials目录
        return f"{root}/{type_dir}/{uuid_str[:2]}/{uuid_str[2:4]}/{uuid_str}.{ext}"

    @staticmethod
    def _normalize_title(title: Optional[str], fallback: str) -> str:
        """标准化标题"""
        final_title = (title or fallback).strip()
        return final_title or fallback

    @staticmethod
    def _upload_fileobj(file_obj, object_name: str, content_type: Optional[str] = None) -> str:
        """直接上传文件到存储，不降级"""
        stream = getattr(file_obj, "file", file_obj)
        if hasattr(stream, "seek"):
            stream.seek(0)
        return get_storage_client().upload_fileobj(stream, object_name, content_type)

    @staticmethod
    def get_path_after_baseurl(url: str, baseurl: str = "https://vidmuse.tos-cn-beijing.volces.com") -> str:
        """从URL中提取存储路径"""
        from urllib.parse import urlparse
        if not url:
            return ""
        if url.startswith(baseurl):
            return url[len(baseurl):].lstrip("/")
        parsed = urlparse(url)
        return parsed.path.lstrip("/")

    def get_pipeline(self) -> Any:
        """获取视频解析流水线
        临时使用ProductParsingPipeline绕过VideoParsingPipeline内部问题，它本身支持视频解析
        """
        from backend.v1.app.pipeline.factory.pipeline_factory import PipelineFactory
        return PipelineFactory.get_direct_video_pipeline()

    def get_asset_id(self, db: Session, video_id: int) -> Optional[int]:
        """根据视频ID获取关联的资产ID"""
        # 注意：这里需要使用同步的DAO方法查询
        from sqlalchemy import select
        from backend.v1.app.admin.video_library.model.video_library import VideoLibrary

        # 使用同步查询，只获取asset_id字段
        result = db.execute(select(VideoLibrary.asset_id).where(VideoLibrary.id == video_id))
        return result.scalar_one_or_none()

    def _get_asset_sync(self, db: Session, asset_id: int) -> Optional[Any]:
        """同步查询资产信息，绕过异步DAO"""
        from sqlalchemy import select
        from backend.v1.app.models.asset import Asset

        result = db.execute(select(Asset).where(Asset.id == asset_id))
        return result.scalar_one_or_none()

    def _update_asset_sync(self, db: Session, asset_id: int, update_data: Dict[str, Any]) -> None:
        """同步更新资产信息，绕过异步DAO"""
        from sqlalchemy import update
        from backend.v1.app.models.asset import Asset

        stmt = update(Asset).where(Asset.id == asset_id).values(**update_data)
        db.execute(stmt)
        db.commit()

    def sync_status(self, db: Session, video_id: int, asset: Any) -> None:
        """同步资产状态到video_library表"""
        from backend.v1.app.admin.video_library.model.video_library import VideoLibrary

        # 使用同步更新
        db.query(VideoLibrary).filter(VideoLibrary.id == video_id).update({
            "execution_id": asset.execution_id,
            "parsing_status": asset.parsing_status,
            "parsing_error": asset.parsing_error
        })
        db.commit()

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
        """上传视频文件
        完全独立实现，不再依赖AssetService
        """
        try:
            sync_db = next(get_sync_db())

            # 1. 检测并验证视频文件
            self.detect_video_type(file)  # 确保是视频类型
            ext = self._validate_video_file(file)

            # 2. 生成存储路径并上传文件
            final_title = self._normalize_title(title, file.filename or "未命名视频")
            object_name = self.generate_video_object_name(ext)
            file_url = self._upload_fileobj(file.file, object_name, file.content_type)

            # 3. 创建资产记录
            asset_data = {
                "user_id": None,  # 视频库资产没有特定所有者
                "type": 2,  # 视频类型
                "title": final_title,
                "url": file_url,
                "file_size": getattr(file, "size", None),
                "duration": None,
                "format": ext,
                "ai_features": None,
                "source_type": 0,  # 内部上传
                "storage_key": object_name,
                "upload_status": "completed",
                "scope": {"type": "library"},
                "parsing_status": "pending"  # 初始状态为待解析
            }
            asset = AssetDAO.create_asset(sync_db, asset_data)
            asset_dict = asset.to_dict()

            # 4. 处理分类关联
            video_data = {
                "title": final_title,
                "description": description,
                "url": file_url,
                "file_size": getattr(file, "size", None),
                "format": ext,
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

            # 5. 创建视频库记录，关联资产ID
            video = await VideoLibraryDAO.create(
                db,
                **video_data
            )

            # 6. 根据trigger_ai_parse参数决定是否触发AI解析
            if trigger_ai_parse:
                # 使用VideoParsingPipeline触发解析
                await self.trigger_parsing(db, video.id,force=True)
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

    async def trigger_parsing(self, db: AsyncSession, video_id: int, force: bool = False, context: Optional[Dict[str, Any]] = None) -> bool:
        """手动触发视频解析，使用VideoParsingPipeline
        独立实现，不依赖统一解析框架
        """
        import logging
        logger = logging.getLogger(__name__)

        # 获取同步数据库会话
        sync_db = next(get_sync_db())
        try:
            logger.info(f"开始触发视频 {video_id} 的解析，force={force}")

            # 1. 先验证视频是否存在（异步DAO方法需要await）
            video_exists = await VideoLibraryDAO.get_by_id(db, video_id)
            if not video_exists:
                logger.error(f"视频 {video_id} 不存在，无法触发解析")
                return False
            logger.info(f"视频 {video_id} 存在，准备查询关联资产")

            # 2. 获取关联的资产ID（使用已有的get_asset_id方法，同步查询）
            asset_id = self.get_asset_id(sync_db, video_id)
            if not asset_id:
                logger.error(f"视频 {video_id} 未关联资产，无法触发解析，请检查video_library表的asset_id字段")
                return False
            logger.info(f"查询到关联资产ID: {asset_id}")

            # 3. 使用同步SQL查询资产信息，绕过异步DAO的问题
            asset = self._get_asset_sync(sync_db, asset_id)
            if not asset:
                logger.error(f"资产 {asset_id} 不存在于asset表中，无法触发解析")
                return False
            logger.info(f"找到资产: id={asset.id}, type={asset.type}, url={asset.url}, status={asset.parsing_status}")

            # 3. 状态检查
            if asset.parsing_status == "completed" and not force and asset.ai_features:
                logger.info(f"资产 {asset_id} 已经解析完成，跳过解析（force={force}）")
                return True

            # 4. 如果有正在运行的解析任务，直接返回
            if asset.parsing_status == "running" and not force:
                logger.info(f"资产 {asset_id} 解析任务正在进行中，跳过重复触发")
                return True

            # 5. 更新状态为待执行
            self._update_asset_sync(sync_db, asset_id, {
                "parsing_status": "pending",
                "parsing_error": None
            })

            # 同步状态到视频库表
            updated_asset = self._get_asset_sync(sync_db, asset_id)
            self.sync_status(sync_db, video_id, updated_asset)

            # 6. 尝试断点恢复（如果有execution_id且不强制重新执行）
            execution_id = asset.execution_id
            pipeline_result = None
            context = context or {}

            if execution_id and not force:
                try:
                    pipeline = self.get_pipeline()
                    logger.info(f"断点恢复-流水线对象类型: {type(pipeline)}")

                    # 确保pipeline是实例而不是类
                    if callable(pipeline) and not hasattr(pipeline, 'resume_execution'):
                        logger.info("断点恢复-流水线返回的是类，正在实例化...")
                        pipeline = pipeline()

                    pipeline_result = pipeline.resume_execution(execution_id)
                    logger.info(f"资产 {asset_id} 断点恢复执行，execution_id={execution_id}")
                except Exception as e:
                    logger.warning(f"资产 {asset_id} 断点恢复失败，将重新执行: {str(e)}")
                    execution_id = None

            # 7. 重新执行完整解析
            if not execution_id or force or not pipeline_result:
                try:
                    pipeline = self.get_pipeline()
                    logger.info(f"流水线对象类型: {type(pipeline)}, 是否是实例: {isinstance(pipeline, object)}")

                    # 构建流水线参数
                    pipeline_params = {
                        "asset_id": asset_id,
                        "asset_url": asset.url,
                        "object_name": self.get_path_after_baseurl(asset.url),
                        "asset_type": asset.type,
                        "video_url": asset.url,  # 视频类型添加video_url字段
                        "video_id": video_id,
                        "business_id": video_id,
                        "business_type": "VideoLibraryService",
                        **context
                    }
                    logger.info(f"流水线参数: {pipeline_params}")

                    # 确保pipeline是实例而不是类
                    if callable(pipeline) and not hasattr(pipeline, 'run_with_persistence'):
                        logger.info("流水线返回的是类，正在实例化...")
                        pipeline = pipeline()

                    pipeline_result = pipeline.run_with_persistence(pipeline_params)
                    logger.info(f"资产 {asset_id} 开始执行新的解析任务，执行ID: {pipeline_result.get('execution_id')}, 成功: {pipeline_result.get('success')}")
                except Exception as e:
                    error_msg = f"解析流水线执行失败: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    # 更新状态为失败
                    self._update_asset_sync(sync_db, asset_id, {
                        "parsing_status": "failed",
                        "parsing_error": error_msg
                    })
                    updated_asset = self._get_asset_sync(sync_db, asset_id)
                    self.sync_status(sync_db, video_id, updated_asset)
                    return False

            # 8. 处理执行结果
            if not pipeline_result.get("success", False):
                error_msg = f"解析失败: {pipeline_result.get('errors', [])}"
                logger.error(f"视频 {video_id} {error_msg}")
                # 更新状态为失败
                update_data = {
                    "parsing_status": "failed",
                    "parsing_error": error_msg
                }
                if "execution_id" in pipeline_result:
                    update_data["execution_id"] = pipeline_result["execution_id"]

                self._update_asset_sync(sync_db, asset_id, update_data)
                updated_asset = self._get_asset_sync(sync_db, asset_id)
                self.sync_status(sync_db, video_id, updated_asset)
                return False

            # 9. 解析成功，更新状态为运行中（异步执行）
            update_data = {"parsing_status": "running"}
            if "execution_id" in pipeline_result:
                update_data["execution_id"] = pipeline_result["execution_id"]

            self._update_asset_sync(sync_db, asset_id, update_data)
            updated_asset = self._get_asset_sync(sync_db, asset_id)
            self.sync_status(sync_db, video_id, updated_asset)

            logger.info(f"视频 {video_id} 解析任务已成功触发，asset_id={asset_id}")
            return True

        except Exception as e:
            logger.error(f"触发解析失败，video_id={video_id}: {str(e)}", exc_info=True)
            return False
        finally:
            sync_db.close()

    async def get_parsing_progress(self, db: AsyncSession, video_id: int) -> Optional[Dict[str, Any]]:
        """查询视频解析进度
        独立实现，不依赖统一解析框架
        """
        # 获取同步数据库会话
        sync_db = next(get_sync_db())
        try:
            # 1. 获取关联的资产ID
            asset_id = self.get_asset_id(sync_db, video_id)
            if not asset_id:
                return None

            # 2. 获取资产基础信息
            asset = self._get_asset_sync(sync_db, asset_id)
            if not asset:
                return None

            # 3. 基础信息
            progress = {
                "video_id": video_id,
                "asset_id": asset_id,
                "parsing_status": asset.parsing_status,
                "execution_id": asset.execution_id,
                "parsing_error": asset.parsing_error,
                "updated_at": asset.updated_at.isoformat() + "Z" if asset.updated_at else None
            }

            # 4. 如果有execution_id，查询详细进度
            if asset.execution_id:
                try:
                    pipeline = self.get_pipeline()
                    execution_status = pipeline.get_execution_status(asset.execution_id)
                    if execution_status:
                        progress["progress_detail"] = {
                            "current_processor": execution_status["current_processor_index"] + 1,
                            "total_processors": execution_status["total_processors"],
                            "progress_percent": round((execution_status["current_processor_index"] + 1) / execution_status["total_processors"] * 100, 2) if execution_status["total_processors"] > 0 else 0,
                            "status": execution_status["status"],
                            "created_at": execution_status["created_at"],
                            "updated_at": execution_status["updated_at"]
                        }
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"查询详细进度失败: {str(e)}")

            return progress
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"查询解析进度失败，video_id={video_id}: {str(e)}", exc_info=True)
            return None
        finally:
            sync_db.close()

    async def retry_parsing(self, db: AsyncSession, video_id: int) -> bool:
        """重试失败的视频解析
        独立实现，不依赖统一解析框架
        """
        import logging
        logger = logging.getLogger(__name__)

        # 获取同步数据库会话
        sync_db = next(get_sync_db())
        try:
            # 获取关联的资产ID
            asset_id = self.get_asset_id(sync_db, video_id)
            if not asset_id:
                logger.warning(f"视频 {video_id} 未关联资产，无法重试解析")
                return False

            # 获取资产信息
            asset = self._get_asset_sync(sync_db, asset_id)
            if not asset:
                logger.warning(f"资产 {asset_id} 不存在，无法重试解析")
                return False

            # 只有失败的任务可以重试
            if asset.parsing_status not in ["failed", None]:
                logger.warning(f"资产 {asset_id} 状态为 {asset.parsing_status}，不需要重试")
                return False

            # 强制重新解析
            return await self.trigger_parsing(db, video_id, force=True)

        except Exception as e:
            logger.error(f"重试解析失败，video_id={video_id}: {str(e)}", exc_info=True)
            return False
        finally:
            sync_db.close()
