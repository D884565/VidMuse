# backend/v1/app/search/core/exceptions.py
class SearchError(Exception):
    """检索模块基础异常"""
    pass

class ChannelError(SearchError):
    """检索渠道异常"""
    def __init__(self, channel_name: str, message: str):
        self.channel_name = channel_name
        super().__init__(f"渠道[{channel_name}]错误: {message}")

class ChannelTimeoutError(ChannelError):
    """检索渠道超时"""
    pass

class ProcessorError(SearchError):
    """处理器异常"""
    def __init__(self, processor_name: str, message: str):
        self.processor_name = processor_name
        super().__init__(f"处理器[{processor_name}]错误: {message}")

class QueryValidationError(SearchError):
    """查询验证失败"""
    pass
