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

from fastapi import Request, Depends
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.LOCAL_STORAGE_ROOT, exist_ok=True)
    from backend.store.database.schema_bootstrap import ensure_product_assets_table

    ensure_product_assets_table()
    yield


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



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="backend.v1.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
