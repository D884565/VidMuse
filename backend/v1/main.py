import subprocess
import logging
from pathlib import Path
from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.framework.web.response import Response
from backend.framework.log.logger import setup_logging
from backend.framework.log.middleware import TraceMiddleware
from backend.framework.web.exception_handler import register_exception_handlers
from backend.v1.app.generate.controller.generation import router as generation_router
from backend.v1.app.user.controller.user_controller import router as user_router
from backend.v1.app.product.controller.product_controller import router as product_router
from backend.v1.app.product.controller.product_category_controller import router as product_category_router
<<<<<<< HEAD
from backend.v1.app.assets.controller.asset_controller import router as asset_router
from backend.v1.app.slice.controller.slice_controller import router as slice_router
=======
# TODO: rag 模块已移除，后续重新集成
# from backend.v1.app.rag.controller.asset_controller import router as asset_router
# TODO: slice 模块依赖 rag，暂时注释
# from backend.v1.app.slice.controller.slice_controller import router as slice_router
>>>>>>> ef2cd102a639b877b80fed22c991ce46b6da0f7b
from backend.v1.app.video.controller.video import router as video_router
from backend.v1.app.merge.controller.merge import router as merge_router
from backend.v1.app.search.rag_trace.controller.trace_controller import router as trace_router

logger = logging.getLogger(__name__)


def _run_alembic_upgrade():
    """启动时自动执行 alembic upgrade head，将数据库表结构升到最新"""
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"[DB] alembic upgrade head 成功: {result.stdout.strip()}")
        else:
            logger.error(f"[DB] alembic upgrade head 失败: {result.stderr.strip()}")
    except Exception as e:
        logger.error(f"[DB] alembic upgrade head 异常: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时自动迁移数据库"""
    _run_alembic_upgrade()
    yield


# 初始化结构化日志
setup_logging()

app = FastAPI(title="VidMuse", version="0.1.0", lifespan=lifespan)

# 注册请求链路追踪中间件
app.add_middleware(TraceMiddleware)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册业务路由
app.include_router(generation_router)
<<<<<<< HEAD
app.include_router(user_router, prefix="/v1")
app.include_router(product_router, prefix="/v1")
app.include_router(product_category_router, prefix="/v1")
app.include_router(asset_router, prefix="/v1")
app.include_router(slice_router, prefix="/v1")
app.include_router(trace_router, prefix="/v1")  # 后台观测系统接口
=======
app.include_router(user_router, prefix="/generate/v1")
app.include_router(product_router, prefix="/rag/v1")
app.include_router(product_category_router, prefix="/rag/v1")
# app.include_router(asset_router, prefix="/rag/v1")  # TODO: rag 模块已移除
# app.include_router(slice_router, prefix="/rag/v1")  # TODO: slice 模块依赖 rag
app.include_router(trace_router, prefix="/admin/v1")  # 后台观测系统接口
>>>>>>> ef2cd102a639b877b80fed22c991ce46b6da0f7b
app.include_router(video_router, prefix="/v1")
app.include_router(merge_router, prefix="/v1")


@app.get("/", response_model=Response)
async def root():
    """测试默认成功响应"""
    # 默认使用 SUCCESS 错误码: 0000000
    return Response.success(data={"message": "Hello World"})



