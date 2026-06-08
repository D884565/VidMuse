"""
解析服务基类
封装通用的解析逻辑，支持多业务模块复用
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import logging

from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import PARAM_ERROR, SYSTEM_ERROR
from backend.v1.app.assets.dao.asset_dao import AssetDAO

# BasePipeline 导入移到函数内部，避免循环导入

logger = logging.getLogger(__name__)


class BaseParsingService(ABC):
    """
    解析服务抽象基类
    所有需要解析功能的业务模块都应该继承此类，实现必要的抽象方法
    """

    @abstractmethod
    def get_pipeline(self, context: Dict[str, Any]) -> 'BasePipeline':
        """
        获取对应的解析流水线实例
        子类必须实现此方法，返回适合该业务场景的流水线

        :param context: 执行上下文，包含业务相关参数
        :return: 解析流水线实例
        """
        # 延迟导入避免循环依赖
        from backend.v1.app.pipeline.base import BasePipeline
        raise NotImplementedError("子类必须实现get_pipeline方法")

    @abstractmethod
    def get_asset_id(self, db: Session, business_id: int, context: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """
        根据业务ID获取关联的资产ID
        子类必须实现此方法，用于找到业务记录关联的资产

        :param db: 数据库会话
        :param business_id: 业务记录ID（如视频ID、素材ID等）
        :param context: 上下文参数，可选
        :return: 关联的资产ID，不存在返回None
        """
        raise NotImplementedError("子类必须实现get_asset_id方法")

    @abstractmethod
    def sync_status(self, db: Session, business_id: int, asset: Any) -> None:
        """
        同步资产状态到业务表
        子类必须实现此方法，将资产的解析状态同步到业务自身的表中

        :param db: 数据库会话
        :param business_id: 业务记录ID
        :param asset: 最新的资产对象
        """
        raise NotImplementedError("子类必须实现sync_status方法")

    def trigger_parsing(
        self,
        db: Session,
        business_id: int,
        force: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        通用触发解析逻辑
        包含状态检查、流水线执行、状态更新等完整流程

        :param db: 数据库会话
        :param business_id: 业务记录ID
        :param force: 是否强制重新解析，即使已经解析完成
        :param context: 额外的上下文参数，传递给流水线
        :return: 是否成功触发
        """
        try:
            # 1. 获取关联的资产ID
            context = context or {}
            asset_id = self.get_asset_id(db, business_id, context)
            asset = None

            # 2. 如果有资产，获取资产信息并验证
            if asset_id:
                asset = AssetDAO.get_asset_by_id(db, asset_id)
                if not asset:
                    logger.warning(f"资产 {asset_id} 不存在，无法触发解析")
                    return False

                # 3. 状态检查
                if asset.parsing_status == "completed" and not force and asset.ai_features:
                    logger.info(f"资产 {asset_id} 已经解析完成，跳过解析（force={force}）")
                    return True

                # 4. 如果有正在运行的解析任务，直接返回
                if asset.parsing_status == "running" and not force:
                    logger.info(f"资产 {asset_id} 解析任务正在进行中，跳过重复触发")
                    return True

                # 5. 更新状态为待执行
                AssetDAO.update_asset(db, asset_id, {
                    "parsing_status": "pending",
                    "parsing_error": None
                })

                # 同步状态到业务表
                updated_asset = AssetDAO.get_asset_by_id(db, asset_id)
                self.sync_status(db, business_id, updated_asset)
            else:
                # 无关联资产场景，检查context中是否有有效内容
                images = context.get("images", [])
                description = context.get("description", "")
                has_valid_content = (images and isinstance(images, list) and len(images) > 0) or \
                                  (description and isinstance(description, str) and description.strip())

                if not has_valid_content:
                    logger.warning(f"业务记录 {business_id} 未关联资产且没有有效内容，无法触发解析")
                    return False

                logger.info(f"业务记录 {business_id} 无关联资产，使用context中的内容进行解析")

            # 6. 尝试断点恢复（如果有execution_id且不强制重新执行）
            execution_id = asset.execution_id if asset else context.get("execution_id")
            pipeline_result = None

            if execution_id and not force:
                try:
                    from backend.v1.app.pipeline.base import BasePipeline
                    pipeline = self.get_pipeline(context)
                    pipeline_result = pipeline.resume_execution(execution_id)
                    logger.info(f"业务记录 {business_id} 断点恢复执行，execution_id={execution_id}")
                except Exception as e:
                    logger.warning(f"业务记录 {business_id} 断点恢复失败，将重新执行: {str(e)}")
                    execution_id = None

            # 7. 重新执行完整解析
            if not execution_id or force or not pipeline_result:
                try:
                    from backend.v1.app.pipeline.base import BasePipeline
                    pipeline = self.get_pipeline(context)
                    # 构建流水线参数
                    pipeline_params = {**context}

                    # 如果有资产，添加资产相关参数
                    if asset and asset_id:
                        from backend.v1.app.assets.service.asset_service import AssetService
                        pipeline_params.update({
                            "asset_id": asset_id,
                            "asset_url": asset.url,
                            "object_name": AssetService.get_path_after_baseurl(asset.url),
                            "asset_type": asset.type
                        })

                        # 根据资产类型自动添加对应字段
                        if asset.type == 1:  # 图片
                            # 合并资产URL到images列表
                            existing_images = pipeline_params.get("images", [])
                            pipeline_params["images"] = [asset.url] + existing_images
                        elif asset.type == 2:  # 视频
                            object_name = AssetService.get_path_after_baseurl(asset.url)
                            pipeline_params["video_url"] = asset.url
                            pipeline_params["video_object_name"] = object_name  # 传入视频对象存储路径
                            pipeline_params["video_duration"] = asset.duration  # 传入视频时长
                        elif asset.type == 3:  # 音频
                            pipeline_params["audio_url"] = asset.url

                    pipeline_result = pipeline.run_with_persistence(pipeline_params)
                    logger.info(f"业务记录 {business_id} 开始执行新的解析任务")
                except Exception as e:
                    error_msg = f"解析流水线执行失败: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    # 更新状态为失败
                    if asset and asset_id:
                        AssetDAO.update_asset(db, asset_id, {
                            "parsing_status": "failed",
                            "parsing_error": error_msg
                        })
                        updated_asset = AssetDAO.get_asset_by_id(db, asset_id)
                        self.sync_status(db, business_id, updated_asset)
                    return False

            # 8. 处理执行结果
            if not pipeline_result.get("success", False):
                error_msg = f"解析失败: {pipeline_result.get('errors', [])}"
                logger.error(f"业务记录 {business_id} {error_msg}")
                # 更新状态为失败
                if asset and asset_id:
                    update_data = {
                        "parsing_status": "failed",
                        "parsing_error": error_msg
                    }
                    if "execution_id" in pipeline_result:
                        update_data["execution_id"] = pipeline_result["execution_id"]

                    AssetDAO.update_asset(db, asset_id, update_data)
                    updated_asset = AssetDAO.get_asset_by_id(db, asset_id)
                    self.sync_status(db, business_id, updated_asset)
                return False

            # 9. 解析成功，更新状态为运行中（异步执行）
            if asset and asset_id:
                update_data = {"parsing_status": "running"}
                if "execution_id" in pipeline_result:
                    update_data["execution_id"] = pipeline_result["execution_id"]

                AssetDAO.update_asset(db, asset_id, update_data)
                updated_asset = AssetDAO.get_asset_by_id(db, asset_id)
                self.sync_status(db, business_id, updated_asset)
            elif "execution_id" in pipeline_result:
                # 无资产场景，execution_id需要业务自己处理
                logger.info(f"业务记录 {business_id} 解析任务已成功触发，execution_id={pipeline_result['execution_id']}")

            logger.info(f"业务记录 {business_id} 解析任务已成功触发" + (f", asset_id={asset_id}" if asset_id else ""))
            return True

        except Exception as e:
            logger.error(f"触发解析失败，business_id={business_id}: {str(e)}", exc_info=True)
            return False

    def get_parsing_progress(
        self,
        db: Session,
        business_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        通用查询解析进度逻辑

        :param db: 数据库会话
        :param business_id: 业务记录ID
        :return: 进度信息，不存在返回None
        """
        try:
            # 获取关联的资产ID
            asset_id = self.get_asset_id(db, business_id)
            if not asset_id:
                return None

            # 复用AssetService的进度查询逻辑
            from backend.v1.app.assets.service.asset_service import AssetService
            progress = AssetService.get_parsing_progress(db=db, asset_id=asset_id)

            # 添加业务ID到返回结果
            progress["business_id"] = business_id
            return progress

        except Exception as e:
            logger.error(f"查询解析进度失败，business_id={business_id}: {str(e)}", exc_info=True)
            return None

    def retry_parsing(
        self,
        db: Session,
        business_id: int
    ) -> bool:
        """
        通用重试失败的解析任务

        :param db: 数据库会话
        :param business_id: 业务记录ID
        :return: 是否成功触发重试
        """
        try:
            # 获取关联的资产ID
            asset_id = self.get_asset_id(db, business_id)

            if asset_id:
                # 有关联资产的场景
                asset = AssetDAO.get_asset_by_id(db, asset_id)
                if not asset:
                    logger.warning(f"资产 {asset_id} 不存在，无法重试解析")
                    return False

                # 只有失败的任务可以重试
                if asset.parsing_status not in ["failed", None]:
                    logger.warning(f"资产 {asset_id} 状态为 {asset.parsing_status}，不需要重试")
                    return False
            else:
                # 无关联资产的场景，直接重试
                logger.info(f"业务记录 {business_id} 无关联资产，直接重试解析")

            # 强制重新解析
            return self.trigger_parsing(db, business_id, force=True)

        except Exception as e:
            logger.error(f"重试解析失败，business_id={business_id}: {str(e)}", exc_info=True)
            return False
