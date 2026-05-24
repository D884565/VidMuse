from fastapi import FastAPI
from backend.framework.web.response import Response
from backend.framework.exceptions.exceptions import (
    BusinessException,
    ValidationException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
)
from backend.framework.web.exception_handler import register_exception_handlers
from backend.framework.exceptions.error_codes import (
    USER_NOT_FOUND,
    PARAM_ERROR,
    UNAUTHORIZED,
    FORBIDDEN,
    RESOURCE_NOT_FOUND,
    SUCCESS,
)
from backend.v1.app.generate.controller.generation import router as generation_router
from backend.v1.app.rag.controller.asset_controller import router as asset_router
from backend.v1.app.rag.controller.project_controller import router as project_router

app = FastAPI(title="VidMuse", version="0.1.0")

# 注册全局异常处理器
register_exception_handlers(app)

# 注册业务路由
app.include_router(generation_router)
app.include_router(asset_router, prefix="/rag/v1")
app.include_router(project_router, prefix="/rag/v1")


@app.get("/", response_model=Response)
async def root():
    """测试默认成功响应"""
    # 默认使用 SUCCESS 错误码: 0000000
    return Response.success(data={"message": "Hello World"})



