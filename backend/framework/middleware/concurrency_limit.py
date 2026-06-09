"""
接口并发限制中间件
基于内存信号量实现，控制每个接口的并发请求数量
支持自定义接口并发数和排队超时
"""
import asyncio
import logging
from typing import Dict, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.v1.app.config.config import settings

logger = logging.getLogger("concurrency_limit.middleware")


class ConcurrencyLimitMiddleware(BaseHTTPMiddleware):
    """
    接口并发限制中间件

    Usage:
        from fastapi import FastAPI
        from backend.framework.middleware.concurrency_limit import ConcurrencyLimitMiddleware

        app = FastAPI()
        app.add_middleware(ConcurrencyLimitMiddleware)
    """

    def __init__(self, app):
        super().__init__(app)
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
        self.default_limit = settings.CONCURRENCY_LIMIT_DEFAULT
        self.timeout = settings.CONCURRENCY_LIMIT_TIMEOUT
        self.custom_limits = settings.CONCURRENCY_LIMIT_CUSTOM
        self.exclude_paths = set(settings.CONCURRENCY_LIMIT_EXCLUDE_PATHS)
        self.enabled = settings.CONCURRENCY_LIMIT_ENABLED

        logger.info(
            f"Concurrency limit middleware initialized: "
            f"enabled={self.enabled}, "
            f"default_limit={self.default_limit}, "
            f"timeout={self.timeout}s, "
            f"custom_limits={len(self.custom_limits)} paths"
        )

    async def dispatch(self, request: Request, call_next):
        # 限流开关关闭，直接放行
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        # 排除不需要限流的路径
        if path in self.exclude_paths:
            return await call_next(request)

        # 获取该接口的并发限制数
        limit = self.custom_limits.get(path, self.default_limit)

        # 获取或创建信号量
        semaphore = self._get_or_create_semaphore(path, limit)
        acquired = False

        try:
            # 尝试获取信号量，超时时间内等待
            await asyncio.wait_for(semaphore.acquire(), timeout=self.timeout)
            acquired = True

            logger.debug(
                f"Acquired semaphore for path={path}, "
                f"current_active={limit - semaphore._value}, "
                f"limit={limit}"
            )

            # 执行请求
            return await call_next(request)

        except asyncio.TimeoutError:
            # 等待超时，返回429错误
            logger.warning(
                f"Concurrency limit exceeded for path={path}, "
                f"limit={limit}, "
                f"timeout={self.timeout}s"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "请求过于频繁，请稍后重试",
                    "data": None
                }
            )
        except Exception as e:
            # 中间件异常（获取信号量阶段），记录日志并放行，避免中间件故障影响业务
            logger.error(f"Concurrency limit middleware error when acquiring semaphore: {str(e)}", exc_info=True)
            return await call_next(request)
        finally:
            # 只有成功获取到信号量的才需要释放
            if acquired:
                try:
                    semaphore.release()
                    logger.debug(
                        f"Released semaphore for path={path}, "
                        f"current_active={limit - semaphore._value}"
                    )
                except Exception as e:
                    logger.error(f"Failed to release semaphore: {str(e)}", exc_info=True)

    def _get_or_create_semaphore(self, path: str, limit: int) -> asyncio.Semaphore:
        """
        获取或创建路径对应的信号量
        如果信号量不存在或者limit变化了，创建新的信号量
        """
        if path not in self.semaphores or self.semaphores[path]._value != limit:
            # 注意：当修改自定义并发数后，需要重启服务才能生效
            self.semaphores[path] = asyncio.Semaphore(limit)
            logger.info(f"Created semaphore for path={path}, limit={limit}")

        return self.semaphores[path]
