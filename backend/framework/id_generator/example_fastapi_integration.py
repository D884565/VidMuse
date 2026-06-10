"""
FastAPI 集成示例
展示如何在FastAPI应用中集成雪花ID生成器
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.framework import (
    initialize_global_generator,
    get_next_id,
    get_next_string_id,
    close_global_generator
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 应用启动时初始化ID生成器
    await initialize_global_generator(
        service_name="vidmuse_service",  # 替换为你的服务名称
        data_center_id=0                 # 替换为你的数据中心ID
    )
    yield
    # 应用关闭时释放资源
    await close_global_generator()


app = FastAPI(lifespan=lifespan)


@app.get("/generate-id")
async def generate_id():
    """
    生成ID接口示例
    """
    id = await get_next_id()
    id_str = await get_next_string_id()
    return {
        "id": id,
        "id_str": id_str
    }


@app.post("/create-resource")
async def create_resource():
    """
    创建资源示例，使用ID生成器作为主键
    """
    resource_id = await get_next_id()
    # 这里可以添加创建资源的逻辑
    return {
        "resource_id": resource_id,
        "message": "Resource created successfully"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
