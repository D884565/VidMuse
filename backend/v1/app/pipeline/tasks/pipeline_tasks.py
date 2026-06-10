"""
流水线Celery任务定义
"""
import logging
from celery import Task
from backend.v1.app.generate.tasks.celery_app import celery_app
from backend.v1.app.pipeline.pipelines import (
    ProductParsingPipeline,
    DirectVideoParsingPipeline
)

logger = logging.getLogger(__name__)


class BasePipelineTask(Task):
    """流水线任务基类"""
    abstract = True
    max_retries = 3
    default_retry_delay = 60  # 重试间隔60秒

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败回调"""
        logger.error(f"流水线任务失败 task_id={task_id}, error={str(exc)}", exc_info=True)
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功回调"""
        logger.info(f"流水线任务成功 task_id={task_id}")
        super().on_success(retval, task_id, args, kwargs)


@celery_app.task(
    bind=True,
    base=BasePipelineTask,
    soft_time_limit=1800,  # 30分钟软超时
    time_limit=2100,  # 35分钟硬超时
    name="product_parsing"
)
def product_parsing_task(self, payload: dict, trace_id: str = None, user_id: int = None):
    """
    商品解析流水线任务
    :param payload: 任务参数，包含商品解析所需的所有数据
    :param trace_id: 链路追踪ID
    :param user_id: 关联用户ID
    :return: 流水线执行结果
    """
    logger.info(f"[商品解析任务启动] trace_id={trace_id}, user_id={user_id}, payload={payload}")

    try:
        # 注入trace_id和user_id到输入数据中，供trace装饰器使用
        input_data = payload.copy()
        if trace_id:
            input_data["trace_id"] = trace_id
        if user_id:
            input_data["user_id"] = user_id
        if "created_by" not in input_data and user_id:
            input_data["created_by"] = str(user_id)

        # 创建并执行流水线
        pipeline = ProductParsingPipeline(
            enable_persistence=True,
            persist_to_asset=True
        )
        result = pipeline.run_with_persistence(input_data)

        if not result["success"]:
            error_msg = "; ".join(result["errors"])
            logger.error(f"商品解析流水线执行失败: {error_msg}")
            raise RuntimeError(f"商品解析失败: {error_msg}")

        logger.info(f"商品解析流水线执行成功, execution_id={result.get('execution_id')}")
        return {
            "success": True,
            "execution_id": result.get("execution_id"),
            "data": result.get("data", {})
        }

    except Exception as e:
        logger.error(f"商品解析任务异常: {str(e)}", exc_info=True)
        # 重试逻辑
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        raise


@celery_app.task(
    bind=True,
    base=BasePipelineTask,
    soft_time_limit=2700,  # 45分钟软超时（视频解析可能耗时较长）
    time_limit=3000,  # 50分钟硬超时
    name="direct_video_parsing"
)
def direct_video_parsing_task(self, payload: dict, trace_id: str = None, user_id: int = None):
    """
    直接视频解析流水线任务
    :param payload: 任务参数，包含视频解析所需的所有数据
    :param trace_id: 链路追踪ID
    :param user_id: 关联用户ID
    :return: 流水线执行结果
    """
    logger.info(f"[直接视频解析任务启动] trace_id={trace_id}, user_id={user_id}, payload={payload}")

    try:
        # 注入trace_id和user_id到输入数据中，供trace装饰器使用
        input_data = payload.copy()
        if trace_id:
            input_data["trace_id"] = trace_id
        if user_id:
            input_data["user_id"] = user_id
        if "created_by" not in input_data and user_id:
            input_data["created_by"] = str(user_id)

        # 创建并执行流水线
        pipeline = DirectVideoParsingPipeline(
            enable_vectorization=True,
            enable_persistence=True
        )
        result = pipeline.run_with_persistence(input_data)

        if not result["success"]:
            error_msg = "; ".join(result["errors"])
            logger.error(f"直接视频解析流水线执行失败: {error_msg}")
            raise RuntimeError(f"视频解析失败: {error_msg}")

        logger.info(f"直接视频解析流水线执行成功, execution_id={result.get('execution_id')}")
        return {
            "success": True,
            "execution_id": result.get("execution_id"),
            "data": result.get("data", {})
        }

    except Exception as e:
        logger.error(f"直接视频解析任务异常: {str(e)}", exc_info=True)
        # 重试逻辑
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        raise
