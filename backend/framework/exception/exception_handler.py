import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import (
    RequestValidationError,
    WebSocketRequestValidationError
)

from pydantic import ValidationError

from .exceptions import BaseAppException, BusinessException
from backend.framework.web.response import Response
from backend.framework.errorcode import (
    PARAM_ERROR,
    SYSTEM_ERROR,
    UNAUTHORIZED,
    FORBIDDEN,
    RESOURCE_NOT_FOUND,
    REQUEST_METHOD_NOT_SUPPORTED,
    RESOURCE_CONFLICT,
    REQUEST_TOO_FREQUENT
)

logger = logging.getLogger(__name__)


def _format_validation_errors(errors) -> list[str]:
    """格式化验证错误信息"""
    formatted_errors = []
    for err in errors:
        field = ".".join(str(loc) for loc in err["loc"])
        formatted_errors.append(f"{field}: {err['msg']}")
    return formatted_errors


async def base_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """自定义基础异常处理器"""
    # 记录异常日志
    logger.info(f"业务异常: code={exc.code}, message={exc.message}, path={request.url.path}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=Response.error(
            code=exc.code,
            message=exc.message,
            data=exc.data
        ).model_dump()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """请求参数验证异常处理器"""
    errors = _format_validation_errors(exc.errors())
    logger.info(f"参数验证异常: path={request.url.path}, errors={errors}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=Response.error(
            code=PARAM_ERROR[0],
            message="参数验证失败",
            data={"errors": errors}
        ).model_dump()
    )


async def websocket_validation_exception_handler(request: Request, exc: WebSocketRequestValidationError) -> JSONResponse:
    """WebSocket 参数验证异常处理器"""
    errors = _format_validation_errors(exc.errors())
    logger.info(f"WebSocket参数验证异常: path={request.url.path}, errors={errors}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=Response.error(
            code=PARAM_ERROR[0],
            message="WebSocket参数验证失败",
            data={"errors": errors}
        ).model_dump()
    )


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Pydantic 验证异常处理器"""
    errors = _format_validation_errors(exc.errors())
    logger.info(f"数据验证异常: path={request.url.path}, errors={errors}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=Response.error(
            code=PARAM_ERROR[0],
            message="数据验证失败",
            data={"errors": errors}
        ).model_dump()
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器，捕获所有未处理的异常"""
    logger.error(f"未处理异常: path={request.url.path}, error={str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=Response.error(
            code=SYSTEM_ERROR[0],
            message=SYSTEM_ERROR[1]
        ).model_dump()
    )


def register_exception_handlers(app):
    """注册所有异常处理器到 FastAPI 应用"""
    app.add_exception_handler(BaseAppException, base_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(WebSocketRequestValidationError, websocket_validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
