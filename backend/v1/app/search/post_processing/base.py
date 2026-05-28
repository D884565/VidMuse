from typing import List, Optional
from ..core import BasePostProcessor, Query, Document, PostProcessingError
from ..config import POST_PROCESSING_CONFIG

class BasePostProcessorImpl(BasePostProcessor):
    """后处理器基类实现"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or POST_PROCESSING_CONFIG

    def process(self, documents: List[Document], query: Query) -> List[Document]:
        """
        处理检索结果，子类需要实现_process方法
        """
        try:
            return self._process(documents, query)
        except Exception as e:
            raise PostProcessingError(f"{self.__class__.__name__} failed: {str(e)}") from e

    def _process(self, documents: List[Document], query: Query) -> List[Document]:
        """
        实际的处理逻辑，子类必须实现此方法
        """
        raise NotImplementedError("Subclasses must implement _process method")
