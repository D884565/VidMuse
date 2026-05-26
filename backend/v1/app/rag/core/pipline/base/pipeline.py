from abc import ABC
from typing import List, Dict, Any
from .processor import BaseProcessor
from .context import PipelineContext


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
        context = PipelineContext(input_data)

        for processor in self.processors:
            if context.has_errors():
                break  # 有错误时终止后续处理
            try:
                context = processor.process(context)
            except Exception as e:
                context.add_error(e)
                break

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
