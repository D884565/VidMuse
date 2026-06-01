from pydantic_settings import BaseSettings, SettingsConfigDict


class TraceConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix=""
    )

    # 是否启用追踪
    TRACE_ENABLED: bool = True
    # 是否记录参数
    TRACE_RECORD_ARGS: bool = True
    # 是否记录返回值
    TRACE_RECORD_RETURN: bool = True
    # 是否记录异常堆栈
    TRACE_RECORD_STACK: bool = True
    # 异步写入批量大小
    TRACE_BATCH_SIZE: int = 100
    # 参数最大长度（超过截断）
    TRACE_MAX_ARG_LENGTH: int = 10000
    # 返回值最大长度（超过截断）
    TRACE_MAX_RETURN_LENGTH: int = 10000


# 全局配置实例
trace_config = TraceConfig()
