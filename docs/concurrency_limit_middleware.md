# 接口并发限制中间件使用说明

## 功能概述
本中间件用于限制每个接口的并发请求数量，防止接口被过多请求压垮。基于内存信号量实现，支持自定义接口并发数和排队超时。

## 配置说明
所有配置都在 `backend/v1/app/config/config.py` 中进行：

### 1. 基础配置
```python
# 并发限制总开关，默认开启
CONCURRENCY_LIMIT_ENABLED: bool = True

# 每个接口默认最大并发数，默认5
CONCURRENCY_LIMIT_DEFAULT: int = 5

# 排队超时时间（秒），默认30秒
CONCURRENCY_LIMIT_TIMEOUT: int = 30
```

### 2. 自定义接口并发数
为特定接口设置不同的并发数：
```python
CONCURRENCY_LIMIT_CUSTOM: dict = {
    "/v1/generate/video": 10,  # 视频生成接口允许10个并发
    "/v1/merge/video": 3,      # 视频合并接口允许3个并发
    "/v1/asset/upload": 20,    # 文件上传接口允许20个并发
}
```

### 3. 排除不需要限流的路径
某些路径（如健康检查、文档页面）不需要限流，可以配置排除：
```python
CONCURRENCY_LIMIT_EXCLUDE_PATHS: list = [
    "/",                # 根路径
    "/docs",            # Swagger文档
    "/openapi.json",    # OpenAPI规范
    "/redoc",           # ReDoc文档
    "/health"           # 健康检查接口（如果有的话）
]
```

## 使用方式
中间件已经在 `main.py` 中自动注册，不需要额外的代码修改。只需调整上述配置即可。

## 错误响应
当请求排队超时时，会返回429状态码：
```json
{
  "code": 429,
  "message": "请求过于频繁，请稍后重试",
  "data": null
}
```

## 日志说明
中间件会记录以下日志：
- 初始化信息：启动时打印配置信息
- 信号量获取/释放：调试级别日志，记录每个接口的当前并发数
- 超限警告：当请求超时时打印警告日志
- 错误日志：中间件异常时打印错误日志

## 注意事项
1. **内存模式限制**：本实现基于内存信号量，仅适用于单实例部署。如果需要多实例部署，请使用Redis分布式版本。
2. **配置生效**：修改 `CONCURRENCY_LIMIT_CUSTOM` 后需要重启服务才能生效。
3. **性能影响**：中间件性能损耗极低，对业务接口的影响可以忽略不计。
4. **超时机制**：超时时间是排队等待的最大时间，不是接口执行时间。接口本身的执行时间不受此限制。

## 示例配置
以下是一个完整的配置示例：
```python
# 接口并发限制配置
CONCURRENCY_LIMIT_ENABLED: bool = True
CONCURRENCY_LIMIT_DEFAULT: int = 5
CONCURRENCY_LIMIT_TIMEOUT: int = 30
CONCURRENCY_LIMIT_CUSTOM: dict = {
    "/v1/generate/video": 8,
    "/v1/merge/video": 2,
    "/v1/asset/upload": 15,
    "/v1/user/login": 50
}
CONCURRENCY_LIMIT_EXCLUDE_PATHS: list = ["/", "/docs", "/openapi.json", "/redoc"]
```
