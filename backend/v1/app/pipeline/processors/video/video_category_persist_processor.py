"""
视频分类信息持久化处理器
将匹配到的分类信息更新到video_library表中
"""
import logging
from typing import Optional
from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
from backend.v1.app.admin.video_library.dao.video_library_dao import VideoLibraryDAO
from backend.store.database.async_database import SessionLocal as async_session
import asyncio

logger = logging.getLogger(__name__)


class VideoCategoryPersistProcessor(BaseProcessor):
    """
    视频分类信息持久化处理器
    将分类匹配处理器输出的分类信息更新到MySQL的video_library表中
    """

    def __init__(self):
        """初始化视频分类持久化处理器"""
        pass

    def _run_async(self, coro):
        """
        从同步上下文中运行异步函数，处理已有事件循环的情况
        :param coro: 要运行的协程
        :return: 协程的返回值
        """
        try:
            # 检查是否有正在运行的事件循环
            loop = asyncio.get_running_loop()
            # 如果有运行中的循环，在新线程中运行异步函数避免死锁
            import threading
            result = None

            def run_in_thread():
                nonlocal result
                # 新线程中创建新的事件循环
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            return result
        except RuntimeError:
            # 没有运行中的循环，直接使用asyncio.run
            return asyncio.run(coro)

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行分类信息持久化逻辑
        从上下文中获取分类信息，更新到video_library表对应的记录中

        输入（从上下文获取）：
        - video_id: str/int 视频ID（初始输入）
        - category_id: int 匹配到的分类ID（CategoryMatchingProcessor输出）
        - category_name: str 分类名称（CategoryMatchingProcessor输出）
        - category_path: str 分类路径（CategoryMatchingProcessor输出）
        - category_name_path: str 分类名称路径（CategoryMatchingProcessor输出）

        输出：
        - 上下文不变，分类信息会被持久化到数据库
        """
        try:
            # 从上下文获取必要字段
            video_id = context.get(constants.VIDEO_ID)
            category_id = context.get("category_id")
            category_name = context.get("category_name")
            category_path = context.get("category_path")
            category_name_path = context.get("category_name_path")

            # 验证必要字段
            if not video_id:
                logger.warning("视频ID不存在，跳过分类信息持久化")
                return context

            if category_id is None:
                logger.warning(f"视频ID: {video_id} 没有匹配到分类，跳过持久化")
                return context

            # 转换video_id为整数
            try:
                video_id_int = int(video_id)
            except (ValueError, TypeError):
                logger.error(f"无效的视频ID格式: {video_id}, 无法转换为整数")
                context.add_error(ValueError(f"无效的视频ID格式: {video_id}"))
                return context

            logger.info(f"开始持久化视频分类信息，video_id: {video_id_int}, category_id: {category_id}, category: {category_name_path}")

            # 异步更新数据库
            async def update_category():
                async with async_session() as db:
                    # 构建更新数据
                    update_data = {
                        "category_id": category_id,
                        "category": category_name_path,  # 存储完整分类名称路径，方便展示
                        "category_path": category_path
                    }

                    # 更新视频记录
                    updated_video = await VideoLibraryDAO.update(db, video_id_int, **update_data)

                    if updated_video:
                        logger.info(f"视频分类信息更新成功，video_id: {video_id_int}, category: {category_name_path}")
                        return True
                    else:
                        logger.warning(f"视频记录不存在，video_id: {video_id_int}")
                        return False

            # 执行异步更新
            success = self._run_async(update_category())

            if success:
                context.metadata["category_persisted"] = True
            else:
                context.metadata["category_persisted"] = False
                context.add_error(ValueError(f"视频分类信息持久化失败，video_id: {video_id}"))

        except Exception as e:
            logger.error(f"视频分类信息持久化失败: {str(e)}", exc_info=True)
            context.add_error(ValueError(f"视频分类信息持久化失败: {str(e)}"))

        return context
