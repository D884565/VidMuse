import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.framework.web.response import Response
from backend.framework.trace import TraceMiddleware
from backend.framework.web.exception_handler import register_exception_handlers
from backend.v1.app.generate.controller.generation import router as generation_router
from backend.v1.app.user.controller.user_controller import router as user_router
from backend.v1.app.product.controller.product_controller import router as product_router
from backend.v1.app.product.controller.product_category_controller import router as product_category_router
from backend.v1.app.video.controller.video import router as video_router
from backend.v1.app.merge.controller.merge import router as merge_router
from backend.v1.app.admin.rag_trace.controller.trace_controller import router as agent_trace_router
from backend.v1.app.admin.video_library.controller.video_library_controller import router as video_library_router
from backend.v1.app.admin.trace_management.controller.trace_management_controller import router as trace_management_router
from backend.v1.app.admin.inspiration_template.controller.inspiration_controller import router as inspiration_template_router
# 推送模块路由
from backend.v1.app.push.controller.websocket_controller import router as ws_router
from backend.v1.app.push.controller.message_controller import router as message_router
from backend.v1.app.slice.controller.slice_controller import router as slice_router
from backend.v1.app.assets.controller.asset_controller import router as asset_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    yield



app = FastAPI(title="VidMuse", version="0.1.0", lifespan=lifespan)

# 注册请求链路追踪中间件
app.add_middleware(TraceMiddleware)

# 注册全局异常处理器
register_exception_handlers(app)


# 注册业务路由
app.include_router(generation_router)

app.include_router(user_router, prefix="/v1")


app.include_router(product_router, prefix="/v1")

app.include_router(product_category_router, prefix="/v1")

app.include_router(asset_router, prefix="/v1")

app.include_router(slice_router, prefix="/v1")

app.include_router(agent_trace_router, prefix="/v1")  # 后台观测系统接口

app.include_router(video_router, prefix="/v1")

app.include_router(merge_router, prefix="/v1")

app.include_router(video_library_router, prefix="/v1")

app.include_router(trace_management_router, prefix="/v1")  # 后台链路追踪管理接口

app.include_router(inspiration_template_router, prefix="/v1")  # 后台灵感模板管理接口

# 注册推送模块路由
app.include_router(ws_router, prefix="/v1")
app.include_router(message_router, prefix="/v1")



@app.get("/", response_model=Response)
async def root():
    """测试默认成功响应"""
    # 默认使用 SUCCESS 错误码: 0000000
    return Response.success(data={"message": "Hello World"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app="backend.v1.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )



