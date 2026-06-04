# backend/v1/app/search/processors/post_processing/base.py
from typing import List, Optional, Dict, Any
import logging
from ...core.interfaces import PostProcessingProcessor
from ...core.models import SearchResult
from ...core.exceptions import ProcessorError

logger = logging.getLogger(__name__)

class BasePostProcessor(PostProcessingProcessor):
    """结果后处理器基类，提供通用功能"""

    def process(self, results: List[SearchResult], context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        同步处理结果，子类重写_process方法实现具体逻辑
        """
        try:
            logger.debug(f"执行后处理器[{self.processor_name}]，输入结果数: {len(results)}")
            processed = self._process(results, context or {})
            logger.debug(f"后处理器[{self.processor_name}]执行完成，输出结果数: {len(processed)}")
            return processed
        except Exception as e:
            logger.error(f"后处理器[{self.processor_name}]执行失败: {str(e)}", exc_info=True)
            raise ProcessorError(self.processor_name, str(e)) from e

    async def aprocess(self, results: List[SearchResult], context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        异步处理结果，子类重写_aprocess方法实现具体逻辑
        """
        try:
            logger.debug(f"异步执行后处理器[{self.processor_name}]，输入结果数: {len(results)}")
            processed = await self._aprocess(results, context or {})
            logger.debug(f"异步后处理器[{self.processor_name}]执行完成，输出结果数: {len(processed)}")
            return processed
        except Exception as e:
            logger.error(f"异步后处理器[{self.processor_name}]执行失败: {str(e)}", exc_info=True)
            raise ProcessorError(self.processor_name, str(e)) from e

    def _process(self, results: List[SearchResult], context: Dict[str, Any]) -> List[SearchResult]:
        """
        同步处理逻辑，子类必须重写此方法或_aprocess
        """
        import asyncio
        return asyncio.run(self._aprocess(results, context))

    async def _aprocess(self, results: List[SearchResult], context: Dict[str, Any]) -> List[SearchResult]:
        """
        异步处理逻辑，子类必须重写此方法或_process
        """
        raise NotImplementedError(f"处理器[{self.processor_name}]未实现_process或_aprocess方法")
