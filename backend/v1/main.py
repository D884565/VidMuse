import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.framework.trace import TraceMiddleware
from backend.framework.middleware.concurrency_limit import ConcurrencyLimitMiddleware
from backend.framework.web.exception_handler import register_exception_handlers
from backend.framework.web.response import Response
from backend.v1.app.admin.inspiration_template.controller.inspiration_controller import router as inspiration_template_router
from backend.v1.app.admin.pipeline.controller.pipeline_controller import router as pipeline_router
from backend.v1.app.admin.rag_trace.controller.trace_controller import router as agent_trace_router
from backend.v1.app.admin.trace_management.controller.trace_management_controller import router as trace_management_router
from backend.v1.app.admin.video_library.controller.video_library_controller import router as video_library_router
from backend.v1.app.assets.controller.asset_controller import router as asset_router
from backend.v1.app.config.config import settings
from backend.v1.app.generate.controller.generation import router as generation_router
from backend.v1.app.generate.controller.retry import router as retry_router
from backend.v1.app.merge.controller.merge import router as merge_router
from backend.v1.app.product.controller.product_category_controller import router as product_category_router
from backend.v1.app.product.controller.product_controller import router as product_router
from backend.v1.app.push.controller.message_controller import router as message_router
from backend.v1.app.push.controller.websocket_controller import router as ws_router
from backend.v1.app.slice.controller.slice_controller import router as slice_router
from backend.v1.app.user.controller.user_controller import router as user_router
from backend.v1.app.video.controller.video import router as video_router
from backend.v1.app.task_scheduler.controller.task_controller import router as task_router
from backend.v1.app.pipeline.controller import pipeline_router as pipeline_task_router

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.v1.app.slice.controller.slice_controller import router as slice_router
from backend.v1.app.assets.controller.asset_controller import router as asset_router
from backend.v1.app.script.controller.script_controller import router as script_router
from backend.v1.app.push.service.connection_manager import connection_manager

from fastapi import Request, Depends
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.LOCAL_STORAGE_ROOT, exist_ok=True)
    from backend.store.database.schema_bootstrap import ensure_product_assets_table, ensure_seed_bgm_assets
    from backend.v1.app.push.service.redis_client import redis_client

    ensure_product_assets_table()
    ensure_seed_bgm_assets()

    # 初始化Redis客户端
    await redis_client.initialize()

    await connection_manager.initialize()


    yield

    # 关闭Redis客户端
    await redis_client.close()


app = FastAPI(title="VidMuse", version="0.1.0", lifespan=lifespan, swagger_ui_parameters={"persistAuthorization": True})
os.makedirs(settings.LOCAL_STORAGE_ROOT, exist_ok=True)
app.mount(settings.LOCAL_STORAGE_URL_PREFIX, StaticFiles(directory=settings.LOCAL_STORAGE_ROOT), name="uploads")

# 添加CORS中间件，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TraceMiddleware)
app.add_middleware(ConcurrencyLimitMiddleware)
register_exception_handlers(app)

app.include_router(generation_router)
app.include_router(retry_router)
app.include_router(user_router, prefix="/v1")
app.include_router(product_router, prefix="/v1")
app.include_router(product_category_router, prefix="/v1")
app.include_router(asset_router, prefix="/v1")
app.include_router(slice_router, prefix="/v1")
app.include_router(agent_trace_router, prefix="/v1")
app.include_router(video_router, prefix="/v1")
app.include_router(merge_router, prefix="/v1")

app.include_router(script_router, prefix="/v1")

app.include_router(video_library_router, prefix="/v1")
app.include_router(trace_management_router, prefix="/v1")
app.include_router(inspiration_template_router, prefix="/v1")
app.include_router(pipeline_router, prefix="/v1")
app.include_router(pipeline_task_router, prefix="/v1")
app.include_router(ws_router, prefix="/v1")
app.include_router(message_router, prefix="/v1")
app.include_router(task_router)

security = HTTPBearer()

@app.get("/", response_model=Response)
async def root():
    return Response.success(data={"message": "Hello World"})



# ==================== 测试接口（开发环境使用）====================
@app.get("/test/cluster/overview", tags=["测试接口"])
async def test_cluster_overview():
    """测试聚类接口，无需认证"""
    from backend.v1.app.admin.inspiration_template.service.cluster_service import cluster_service
    from backend.store.database.async_database import get_db

    # 获取数据库会话
    db_gen = get_db()
    db = await db_gen.__anext__()

    try:
        result = await cluster_service.get_overview(db)
        return Response.success(data=result)
    finally:
        await db.close()

@app.post("/test/cluster/run", tags=["测试接口"])
async def test_run_cluster(
    max_vectors: int = 800,
    cluster_eps: float = 0.2,
    min_samples: int = 3
):
    """测试运行聚类分析，无需认证"""
    from backend.v1.app.admin.inspiration_template.service.cluster_service import cluster_service

    params = {
        "max_vectors": max_vectors,
        "cluster_eps": cluster_eps,
        "min_samples": min_samples
    }
    result = await cluster_service.run_analysis(params)
    return Response.success(data=result, message="聚类分析任务已启动")

@app.get("/test/cluster/status", tags=["测试接口"])
async def test_cluster_status(task_id: str = None):
    """测试获取聚类任务状态，无需认证"""
    from backend.v1.app.admin.inspiration_template.service.cluster_service import cluster_service

    result = cluster_service.get_analysis_status(task_id)
    return Response.success(data=result)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="backend.v1.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
