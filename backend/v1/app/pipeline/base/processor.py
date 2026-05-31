from abc import ABC, abstractmethod
from typing import Any, Dict
from .context import PipelineContext


class BaseProcessor(ABC):
    """
    处理器抽象基类
    所有具体处理器必须继承此类并实现process方法
    """

    @abstractmethod
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理上下文数据并返回修改后的上下文

        :param context: 流水线上下文对象
        :return: 修改后的上下文对象
        """
        pass
