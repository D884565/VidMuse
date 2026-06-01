"""链路追踪配置"""
from pydantic_settings import BaseSettings


class TraceConfig(BaseSettings):
    """链路追踪配置类"""
    # 是否开启链路追踪
    TRACE_ENABLED: bool = True

    # 是否记录方法参数
    TRACE_RECORD_ARGS: bool = True
    # 参数最大长度
    TRACE_MAX_ARG_LENGTH: int = 1000

    # 是否记录返回值
    TRACE_RECORD_RETURN: bool = True
    # 返回值最大长度
    TRACE_MAX_RETURN_LENGTH: int = 2000

    # 是否记录堆栈信息
    TRACE_RECORD_STACK: bool = True

    # 批量写入大小
    TRACE_BATCH_SIZE: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = True


trace_config = TraceConfig()
