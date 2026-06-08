import logging
import time
import traceback
from abc import ABC
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from backend.framework.trace.decorator import _sync_push
from .processor import BaseProcessor
from .context import PipelineContext
from ..dao.pipeline_execution_dao import PipelineExecutionDAO
from backend.v1.app.models.pipeline_execution import PipelineExecutionStatus
from backend.store.database.sync_database import get_db
from backend.framework.trace import trace, PushConfig

logger = logging.getLogger(__name__)


# ==================== Trace推送配置 ====================
def _get_pipeline_user_id(*args, **kwargs) -> int:
    """从流水线输入参数中获取user_id"""
    if args and len(args) >= 1 and isinstance(args[0], dict):
        return args[0].get("user_id", 0)
    return kwargs.get("user_id", 0)


def _pipeline_start_msg(func, args, kwargs) -> Tuple[str, str, Dict]:
    """流水线开始执行消息"""
    input_data = args[0] if args else kwargs
    pipeline_type = getattr(func.__self__, 'pipeline_type', 'unknown') if hasattr(func, '__self__') else 'unknown'
    return (
        "pipeline_progress",
        f"{pipeline_type}流水线开始执行",
        {
            "pipeline_type": pipeline_type,
            "status": "running",
            "progress": 0,
            "total_processors": len(getattr(func.__self__, 'processors', [])) if hasattr(func, '__self__') else 0,
            "video_id": input_data.get("video_id"),
            "product_id": input_data.get("product_id"),
            "asset_id": input_data.get("asset_id")
        }
    )


def _pipeline_end_msg(func, result) -> Tuple[str, str, Dict]:
    """流水线执行成功消息"""
    pipeline_type = getattr(func.__self__, 'pipeline_type', 'unknown') if hasattr(func, '__self__') else 'unknown'
    return (
        "pipeline_progress",
        f"{pipeline_type}流水线执行完成",
        {
            "pipeline_type": pipeline_type,
            "status": "completed",
            "progress": 100,
            "success": result.get("success", False),
            "execution_id": result.get("execution_id")
        }
    )


def _pipeline_error_msg(func, exception) -> Tuple[str, str, Dict]:
    """流水线执行失败消息"""
    pipeline_type = getattr(func.__self__, 'pipeline_type', 'unknown') if hasattr(func, '__self__') else 'unknown'
    return (
        "pipeline_progress",
        f"{pipeline_type}流水线执行失败",
        {
            "pipeline_type": pipeline_type,
            "status": "failed",
            "error": str(exception),
            "progress": 0
        },
        "error"
    )


def _get_resume_user_id(*args, **kwargs) -> int:
    """从恢复执行的参数中获取user_id（通过查询execution记录）"""
    if args and len(args) >= 2 and isinstance(args[1], str):
        execution_id = args[1]
        try:
            from backend.store.database.sync_database import get_db
            from backend.v1.app.pipeline.dao.pipeline_execution_dao import PipelineExecutionDAO
            db = next(get_db())
            execution = PipelineExecutionDAO.get_execution_by_id(db, execution_id)
            db.close()
            if execution and execution.input_params:
                return execution.input_params.get("user_id", 0)
        except Exception as e:
            logger.warning(f"Failed to get user_id from execution: {e}")
    return 0


def _resume_start_msg(func, args, kwargs) -> Tuple[str, str, Dict]:
    """流水线恢复执行开始消息"""
    execution_id = args[1] if len(args) >= 2 else "unknown"
    pipeline_type = getattr(func.__self__, 'pipeline_type', 'unknown') if hasattr(func, '__self__') else 'unknown'
    return (
        "pipeline_progress",
        f"{pipeline_type}流水线恢复执行",
        {
            "pipeline_type": pipeline_type,
            "status": "running",
            "execution_id": execution_id,
            "progress": 0
        }
    )


def _resume_end_msg(func, result) -> Tuple[str, str, Dict]:
    """流水线恢复执行成功消息"""
    pipeline_type = getattr(func.__self__, 'pipeline_type', 'unknown') if hasattr(func, '__self__') else 'unknown'
    return (
        "pipeline_progress",
        f"{pipeline_type}流水线恢复执行完成",
        {
            "pipeline_type": pipeline_type,
            "status": "completed",
            "progress": 100,
            "success": result.get("success", False),
            "execution_id": result.get("execution_id")
        }
    )


def _resume_error_msg(func, exception) -> Tuple[str, str, Dict]:
    """流水线恢复执行失败消息"""
    pipeline_type = getattr(func.__self__, 'pipeline_type', 'unknown') if hasattr(func, '__self__') else 'unknown'
    return (
        "pipeline_progress",
        f"{pipeline_type}流水线恢复执行失败",
        {
            "pipeline_type": pipeline_type,
            "status": "failed",
            "error": str(exception),
            "progress": 0
        },
        "error"
    )


class BasePipeline:
    """
    流水线基类
    所有具体流水线必须继承此类，通过组合多个处理器实现完整处理流程
    """

    def __init__(self, processors: List[BaseProcessor],
                 enable_persistence: bool = True,
                 persist_after_each_processor: bool = True,
                 persist_on_error: bool = True,
                 pipeline_type: Optional[str] = None):
        """
        初始化流水线

        :param processors: 处理器列表，将按顺序执行
        :param enable_persistence: 是否开启持久化功能，默认True
        :param persist_after_each_processor: 每个处理器执行完成后是否持久化，默认True
        :param persist_on_error: 发生错误时是否持久化，默认True
        :param pipeline_type: 流水线类型，用于持久化记录，子类应重写此参数
        """
        self.processors = processors
        self.enable_persistence = enable_persistence
        self.persist_after_each_processor = persist_after_each_processor
        self.persist_on_error = persist_on_error
        self.pipeline_type = pipeline_type or self.__class__.__name__

        # 初始化trace推送配置（与run_with_persistence的装饰器配置保持一致）
        self._push_config = PushConfig(
            enable_push=True,
            user_id_getter=_get_pipeline_user_id,
            push_on_start=True,
            push_on_end=True,
            push_on_error=True,
            start_message_generator=_pipeline_start_msg,
            end_message_generator=_pipeline_end_msg,
            error_message_generator=_pipeline_error_msg
        )

    def run(self, input_data: Dict[str, Any], start_from_index: int = 0) -> Dict[str, Any]:
        """
        执行完整的流水线处理流程

        :param input_data: 初始输入数据
        :param start_from_index: 从指定处理器索引开始执行，默认从0开始
        :return: 处理结果，包含success标记、数据、错误信息和元数据
        """
        return self._run_internal(input_data, start_from_index=start_from_index)

    def _run_internal(self,
                     input_data: Dict[str, Any],
                     start_from_index: int = 0,
                     execution_id: Optional[str] = None,
                     db_session: Optional[Session] = None,
                     existing_context: Optional[PipelineContext] = None) -> Dict[str, Any]:
        """
        内部执行方法，支持断点续跑和持久化

        :param input_data: 初始输入数据
        :param start_from_index: 从指定处理器索引开始执行
        :param execution_id: 执行记录ID，用于持久化
        :param db_session: 数据库会话，用于持久化
        :param existing_context: 已有的上下文对象，用于恢复执行
        :return: 处理结果
        """
        pipeline_name = self.__class__.__name__
        logger.info(f"开始执行流水线: {pipeline_name}, 处理器数量: {len(self.processors)}, 开始索引: {start_from_index}")

        if existing_context:
            context = existing_context
            # 合并输入数据到上下文，仅添加不存在的key，避免覆盖已有处理结果
            for key, value in input_data.items():
                if key not in context.data:
                    context.data[key] = value
                else:
                    logger.debug(f"恢复执行时跳过已存在的上下文key: {key}，保留原有值")
        else:
            context = PipelineContext(input_data)

        start_time = time.time()
        current_index = start_from_index - 1  # 初始化为start_from_index的前一个，表示还未开始执行当前批次的处理器

        try:
            for i in range(start_from_index, len(self.processors)):
                current_index = i
                processor = self.processors[i]
                processor_name = processor.__class__.__name__

                if context.has_errors():
                    logger.warning(f"流水线 {pipeline_name} 因错误终止，跳过后续处理器: {processor_name}")
                    break  # 有错误时终止后续处理

                logger.info(f"执行处理器 {i+1}/{len(self.processors)}: {processor_name}")
                processor_start_time = time.time()

                try:
                    context = processor.process(context)
                    processor_duration = time.time() - processor_start_time
                    logger.info(f"处理器 {processor_name} 执行完成，耗时: {processor_duration:.2f}s")

                    # 记录上下文大小变化，便于排查内存问题
                    context_size = len(str(context.data)) + len(str(context.metadata))
                    logger.debug(f"处理器 {processor_name} 执行后上下文大小: {context_size} bytes")

                    # 持久化当前状态
                    if execution_id and db_session and self.persist_after_each_processor:
                        self._persist_progress(db_session, execution_id, current_index, context)

                    # 推送进度更新
                    try:
                        user_id = _get_pipeline_user_id(input_data)
                        if user_id > 0:
                            # 计算进度百分比
                            progress = int((current_index + 1) / len(self.processors) * 100)
                            # 使用trace包的同步推送方法
                            _sync_push(
                                self._push_config,
                                user_id,
                                lambda *args: (
                                    "pipeline_progress",
                                    f"{self.pipeline_type}流水线处理中",
                                    {
                                        "pipeline_type": self.pipeline_type,
                                        "status": "running",
                                        "progress": progress,
                                        "current_processor": processor_name,
                                        "current_index": current_index + 1,
                                        "total_processors": len(self.processors),
                                        "execution_id": execution_id
                                    }
                                )
                            )
                    except Exception as e:
                        logger.warning(f"Failed to push pipeline progress: {e}")

                except Exception as e:
                    processor_duration = time.time() - processor_start_time
                    error_msg = f"处理器 {processor_name} 执行失败，耗时: {processor_duration:.2f}s，错误: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    context.add_error(e)

                    # 持久化错误状态
                    if execution_id and db_session and self.persist_on_error:
                        self._persist_progress(db_session, execution_id, current_index, context)
                        PipelineExecutionDAO.update_execution_status(
                            db_session, execution_id, PipelineExecutionStatus.FAILED, str(e)
                        )
                    break

            total_duration = time.time() - start_time
            success = not context.has_errors()
            logger.info(f"流水线 {pipeline_name} 执行完成，结果: {'成功' if success else '失败'}, 总耗时: {total_duration:.2f}s")

            # 持久化最终结果
            if execution_id and db_session:
                result = self._build_result(context)
                if success:
                    # 所有处理器执行成功，更新current_processor_index为总处理器数量，表示全部完成
                    if not context.has_errors() and current_index == len(self.processors) - 1:
                        self._persist_progress(db_session, execution_id, len(self.processors), context)

                    PipelineExecutionDAO.update_execution_status(
                        db_session, execution_id, PipelineExecutionStatus.COMPLETED
                    )
                    PipelineExecutionDAO.update_execution_result(db_session, execution_id, result)
                else:
                    # 如果还没标记为失败（比如在循环外出错）
                    PipelineExecutionDAO.update_execution_status(
                        db_session, execution_id, PipelineExecutionStatus.FAILED,
                        context.get_errors()[0] if context.get_errors() else "未知错误"
                    )

            if success:
                logger.debug(f"流水线执行结果: {self._build_result(context)}")

            return self._build_result(context)

        except Exception as e:
            # 捕获执行过程中的所有异常，确保状态正确更新
            error_msg = f"流水线执行发生未预期错误: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            context.add_error(e)

            if execution_id and db_session:
                self._persist_progress(db_session, execution_id, current_index, context)
                PipelineExecutionDAO.update_execution_status(
                    db_session, execution_id, PipelineExecutionStatus.FAILED, str(e)
                )

            return self._build_result(context)

    def _build_result(self, context: PipelineContext) -> Dict[str, Any]:
        """
        构建最终返回结果

        :param context: 处理完成后的上下文
        :return: 标准化的结果字典
        """
        return {
            "success": not context.has_errors(),
            "data": context.data,
            "errors": context.get_errors(),
            "metadata": context.metadata
        }

    def _persist_progress(self, db: Session, execution_id: str, current_index: int, context: PipelineContext) -> None:
        """
        持久化当前执行进度

        :param db: 数据库会话
        :param execution_id: 执行ID
        :param current_index: 当前执行到的处理器索引
        :param context: 上下文对象
        """
        try:
            PipelineExecutionDAO.update_execution_progress(
                db,
                execution_id=execution_id,
                current_processor_index=current_index,
                context_data=context.data,
                context_metadata=context.metadata,
                errors=context.get_errors()
            )
        except Exception as e:
            logger.error(f"持久化执行进度失败: {str(e)}", exc_info=True)
            # 持久化失败不影响流水线执行，只记录日志

    @trace(
        push_config=PushConfig(
            enable_push=True,
            user_id_getter=_get_pipeline_user_id,
            push_on_start=True,
            push_on_end=True,
            push_on_error=True,
            start_message_generator=_pipeline_start_msg,
            end_message_generator=_pipeline_end_msg,
            error_message_generator=_pipeline_error_msg
        )
    )
    def run_with_persistence(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行流水线并开启持久化，支持断点续跑

        :param input_data: 初始输入数据
        :return: 执行结果，包含execution_id
        """
        if not self.enable_persistence:
            logger.warning("持久化功能未开启，将直接执行流水线")
            return self.run(input_data)

        pipeline_name = self.__class__.__name__
        db = next(get_db())
        execution_id = None

        try:
            # 创建执行记录
            execution = PipelineExecutionDAO.create_execution(
                db,
                pipeline_name=pipeline_name,
                pipeline_type=self.pipeline_type,
                input_params=input_data,
                total_processors=len(self.processors)
            )
            execution_id = execution.execution_id
            logger.info(f"创建流水线执行记录: {execution_id}")

            # 更新状态为运行中
            PipelineExecutionDAO.update_execution_status(db, execution_id, PipelineExecutionStatus.RUNNING)

            # 执行流水线
            result = self._run_internal(
                input_data,
                start_from_index=0,
                execution_id=execution_id,
                db_session=db
            )

            # 将execution_id加入结果
            result["execution_id"] = execution_id
            return result

        except Exception as e:
            error_msg = f"流水线持久化执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if execution_id:
                try:
                    PipelineExecutionDAO.update_execution_status(
                        db, execution_id, PipelineExecutionStatus.FAILED, error_msg
                    )
                except:
                    pass
            return {
                "success": False,
                "data": {},
                "errors": [error_msg],
                "metadata": {},
                "execution_id": execution_id
            }
        finally:
            db.close()

    @trace(
        push_config=PushConfig(
            enable_push=True,
            user_id_getter=_get_resume_user_id,
            push_on_start=True,
            push_on_end=True,
            push_on_error=True,
            start_message_generator=_resume_start_msg,
            end_message_generator=_resume_end_msg,
            error_message_generator=_resume_error_msg
        )
    )
    def resume_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        从断点恢复执行流水线

        :param execution_id: 执行记录ID
        :return: 执行结果
        """
        if not self.enable_persistence:
            raise RuntimeError("持久化功能未开启，无法恢复执行")

        db = next(get_db())
        try:
            # 查询执行记录
            execution = PipelineExecutionDAO.get_execution_by_id(db, execution_id)
            if not execution:
                raise ValueError(f"执行记录不存在: {execution_id}")

            # 验证状态
            if execution.status == PipelineExecutionStatus.COMPLETED:
                logger.warning(f"执行记录 {execution_id} 已完成，直接返回结果")
                return execution.result or {
                    "success": True,
                    "data": execution.context_data,
                    "errors": [],
                    "metadata": execution.context_metadata,
                    "execution_id": execution_id
                }

            if execution.status not in [PipelineExecutionStatus.FAILED, PipelineExecutionStatus.PENDING]:
                raise ValueError(f"执行记录 {execution_id} 状态为 {execution.status}，无法恢复执行")

            # 验证处理器数量匹配
            if execution.total_processors != len(self.processors):
                raise ValueError(
                    f"处理器数量不匹配: 历史记录有 {execution.total_processors} 个处理器，"
                    f"当前流水线有 {len(self.processors)} 个处理器"
                )

            # 恢复上下文
            context = PipelineContext.from_dict({
                "data": execution.context_data or {},
                "errors": execution.errors or [],
                "metadata": execution.context_metadata or {}
            })

            # 计算开始索引
            if execution.status == PipelineExecutionStatus.FAILED and execution.current_processor_index >= 0:
                # 失败状态，需要重新执行失败的处理器
                start_from_index = execution.current_processor_index
            else:
                # 其他状态，从下一个处理器开始
                start_from_index = execution.current_processor_index + 1

            if start_from_index >= len(self.processors):
                logger.warning(f"所有处理器已执行完成，直接返回结果")
                return self._build_result(context)

            logger.info(f"恢复执行流水线 {execution_id}，从处理器索引 {start_from_index} 开始")

            # 更新状态为运行中
            PipelineExecutionDAO.update_execution_status(db, execution_id, PipelineExecutionStatus.RUNNING)

            # 执行流水线
            result = self._run_internal(
                execution.input_params,
                start_from_index=start_from_index,
                execution_id=execution_id,
                db_session=db,
                existing_context=context
            )

            result["execution_id"] = execution_id
            return result

        except Exception as e:
            error_msg = f"恢复流水线执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "data": {},
                "errors": [error_msg],
                "metadata": {},
                "execution_id": execution_id
            }
        finally:
            db.close()

    @staticmethod
    def get_execution_status(execution_id: str) -> Optional[Dict[str, Any]]:
        """
        查询执行记录状态

        :param execution_id: 执行ID
        :return: 执行状态信息
        """
        db = next(get_db())
        try:
            execution = PipelineExecutionDAO.get_execution_by_id(db, execution_id)
            return execution.to_dict() if execution else None
        finally:
            db.close()
