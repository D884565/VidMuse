# backend/v1/app/search/processors/query_enhancement/base.py
from typing import Optional, Dict, Any
import logging
from ...core.interfaces import QueryEnhancementProcessor
from ...core.models import SearchQuery
from ...core.exceptions import ProcessorError

logger = logging.getLogger(__name__)

class BaseQueryProcessor(QueryEnhancementProcessor):
    """查询增强处理器基类，提供通用功能"""

    def process(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> SearchQuery:
        """
        同步处理查询，子类重写_process方法实现具体逻辑
        """
        try:
            logger.debug(f"执行查询处理器[{self.processor_name}]")
            return self._process(query, context or {})
        except Exception as e:
            logger.error(f"查询处理器[{self.processor_name}]执行失败: {str(e)}", exc_info=True)
            raise ProcessorError(self.processor_name, str(e)) from e

    async def aprocess(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> SearchQuery:
        """
        异步处理查询，子类重写_aprocess方法实现具体逻辑
        """
        try:
            logger.debug(f"异步执行查询处理器[{self.processor_name}]")
            return await self._aprocess(query, context or {})
        except Exception as e:
            logger.error(f"异步查询处理器[{self.processor_name}]执行失败: {str(e)}", exc_info=True)
            raise ProcessorError(self.processor_name, str(e)) from e

    def _process(self, query: SearchQuery, context: Dict[str, Any]) -> SearchQuery:
        """
        同步处理逻辑，子类必须重写此方法或_process
        """
        # 默认实现调用异步方法（同步包装）
        import asyncio
        return asyncio.run(self._aprocess(query, context))

    async def _aprocess(self, query: SearchQuery, context: Dict[str, Any]) -> SearchQuery:
        """
        异步处理逻辑，子类必须重写此方法或_process
        """
        raise NotImplementedError(f"处理器[{self.processor_name}]未实现_process或_aprocess方法")
