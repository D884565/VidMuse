# examples/push_example.py
"""
推送模块使用示例
"""
import asyncio
from sqlalchemy.orm import Session
from backend.framework.db.session import SessionLocal
from backend.v1.app.push import push_service


async def example_push_agent_progress(user_id: int):
    """推送Agent执行进度示例"""
    db = SessionLocal()

    try:
        # 推送开始消息
        await push_service.push_message(
            db=db,
            user_id=user_id,
            message_type="agent_progress",
            title="开始处理您的请求",
            content={
                "step": "start",
                "progress": 0,
                "session_id": "session_123456"
            },
            level="info"
        )

        # 模拟执行步骤
        await asyncio.sleep(1)

        # 推送工具调用消息
        await push_service.push_message(
            db=db,
            user_id=user_id,
            message_type="agent_progress",
            title="正在查询商品信息",
            content={
                "step": "tool_call",
                "tool_name": "product_search",
                "progress": 30,
                "query": "夏季连衣裙"
            },
            level="info"
        )

        await asyncio.sleep(1)

        # 推送思考消息
        await push_service.push_message(
            db=db,
            user_id=user_id,
            message_type="agent_progress",
            title="AI正在生成文案",
            content={
                "step": "thinking",
                "progress": 60,
                "model": "claude-3-opus"
            },
            level="info"
        )

        await asyncio.sleep(1)

        # 推送完成消息
        await push_service.push_message(
            db=db,
            user_id=user_id,
            message_type="agent_progress",
            title="处理完成",
            content={
                "step": "complete",
                "progress": 100,
                "result_url": "/result/123456"
            },
            level="success"
        )

        print("消息推送完成")

    finally:
        db.close()


async def example_push_task_status(user_id: int):
    """推送任务状态示例"""
    db = SessionLocal()

    try:
        await push_service.push_message(
            db=db,
            user_id=user_id,
            message_type="task_status",
            title="视频生成任务完成",
            content={
                "task_id": 123,
                "task_type": "video_generate",
                "status": "completed",
                "progress": 100,
                "video_url": "/video/123/output.mp4",
                "duration": 15.5
            },
            level="success"
        )
    finally:
        db.close()


if __name__ == "__main__":
    # 测试推送给用户ID为1的用户
    asyncio.run(example_push_agent_progress(user_id=1))
    # asyncio.run(example_push_task_status(user_id=1))
