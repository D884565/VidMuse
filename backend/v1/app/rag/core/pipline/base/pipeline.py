import logging
import time
from abc import ABC
from typing import List, Dict, Any
from .processor import BaseProcessor
from .context import PipelineContext

logger = logging.getLogger(__name__)


class BasePipeline(ABC):
    """
    流水线抽象基类
    所有具体流水线必须继承此类，通过组合多个处理器实现完整处理流程
    """

    def __init__(self, processors: List[BaseProcessor]):
        """
        初始化流水线

        :param processors: 处理器列表，将按顺序执行
        """
        self.processors = processors

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行完整的流水线处理流程

        :param input_data: 初始输入数据
        :return: 处理结果，包含success标记、数据、错误信息和元数据
        """
        pipeline_name = self.__class__.__name__
        logger.info(f"开始执行流水线: {pipeline_name}, 处理器数量: {len(self.processors)}")

        context = PipelineContext(input_data)
        start_time = time.time()

        for i, processor in enumerate(self.processors):
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

            except Exception as e:
                processor_duration = time.time() - processor_start_time
                error_msg = f"处理器 {processor_name} 执行失败，耗时: {processor_duration:.2f}s，错误: {str(e)}"
                logger.error(error_msg, exc_info=True)
                context.add_error(e)
                break

        total_duration = time.time() - start_time
        success = not context.has_errors()
        logger.info(f"流水线 {pipeline_name} 执行完成，结果: {'成功' if success else '失败'}, 总耗时: {total_duration:.2f}s")

        if success:
            logger.debug(f"流水线执行结果: {self._build_result(context)}")

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
