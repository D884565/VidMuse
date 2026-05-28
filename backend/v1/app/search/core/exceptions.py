class SearchBaseException(Exception):
    """检索系统基础异常"""
    def __init__(self, message: str = "检索系统错误"):
        self.message = message
        super().__init__(self.message)

class QueryEnhancementError(SearchBaseException):
    """问题增强错误"""
    def __init__(self, message: str = "问题增强处理失败"):
        super().__init__(message)

class RetrievalError(SearchBaseException):
    """检索错误"""
    def __init__(self, message: str = "检索执行失败"):
        super().__init__(message)

class PostProcessingError(SearchBaseException):
    """后处理错误"""
    def __init__(self, message: str = "结果后处理失败"):
        super().__init__(message)

class ConfigurationError(SearchBaseException):
    """配置错误"""
    def __init__(self, message: str = "配置错误"):
        super().__init__(message)

class DataSourceError(SearchBaseException):
    """数据源错误"""
    def __init__(self, message: str = "数据源连接或查询错误"):
        super().__init__(message)
