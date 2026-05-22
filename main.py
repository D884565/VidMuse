from fastapi import FastAPI
from backend.framework import (
    Response,
    BusinessException,
    ValidationException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    register_exception_handlers,
    USER_NOT_FOUND,
    PARAM_ERROR,
    UNAUTHORIZED,
    FORBIDDEN,
    RESOURCE_NOT_FOUND,
    SUCCESS
)
from backend.app.api.v1.generation import router as generation_router

app = FastAPI(title="VidMuse", version="0.1.0")

# 注册全局异常处理器
register_exception_handlers(app)

# 注册业务路由
app.include_router(generation_router)


@app.get("/", response_model=Response)
async def root():
    """测试默认成功响应"""
    # 默认使用 SUCCESS 错误码: 0000000
    return Response.success(data={"message": "Hello World"})


@app.get("/custom-success", response_model=Response)
async def custom_success():
    """测试自定义成功响应"""
    return Response.success(
        data={"user": "test"},
        message="操作完成",
        code=SUCCESS[0]  # 也可以指定其他成功码
    )


@app.get("/hello/{name}", response_model=Response)
async def say_hello(name: str):
    if not name.strip():
        # 使用错误码常量 + 自定义消息
        raise BusinessException(PARAM_ERROR, message="姓名不能为空")
    return Response.success(data={"message": f"Hello {name}"})


@app.get("/user/{user_id}", response_model=Response)
async def get_user(user_id: int):
    """测试使用错误码元组"""
    if user_id <= 0:
        # 直接传入错误码元组
        raise ValidationException(PARAM_ERROR)
    if user_id > 100:
        # 传入错误码元组和自定义消息
        raise BusinessException(USER_NOT_FOUND, f"用户 {user_id} 不存在")
    return Response.success(data={"id": user_id, "name": "测试用户"})


@app.get("/auth", response_model=Response)
async def test_auth():
    """测试未授权异常"""
    raise UnauthorizedException(UNAUTHORIZED)


@app.get("/forbidden", response_model=Response)
async def test_forbidden():
    """测试禁止访问异常"""
    raise ForbiddenException(FORBIDDEN)


@app.get("/not-found", response_model=Response)
async def test_not_found():
    """测试资源不存在异常"""
    raise NotFoundException(RESOURCE_NOT_FOUND)


@app.get("/default-business-error", response_model=Response)
async def test_default_business_error():
    """测试业务异常默认错误码"""
    raise BusinessException(message="自定义业务错误消息")


from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    age: int

@app.post("/user", response_model=Response)
async def create_user(user: UserCreate):
    """测试参数验证"""
    return Response.success(data=user.model_dump())
