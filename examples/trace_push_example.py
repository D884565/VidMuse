"""
Trace注解推送功能使用示例
展示如何通过@trace注解配置实现零侵入的消息推送
"""
import asyncio
from backend.framework.trace import trace, PushConfig


# ==============================
# 示例1：Agent执行函数自动推送进度
# ==============================

def get_user_id_from_args(*args, **kwargs):
    """从函数参数中提取用户ID"""
    return kwargs.get("user_id") or args[0] if args else None


def generate_start_message(func, args, kwargs):
    """生成函数开始执行的推送消息"""
    return (
        "agent_progress",
        "开始处理您的请求",
        {
            "step": "start",
            "progress": 0,
            "session_id": kwargs.get("session_id"),
            "user_input": kwargs.get("user_input")
        }
    )


def generate_end_message(func, result):
    """生成函数执行成功的推送消息"""
    return (
        "agent_progress",
        "处理完成",
        {
            "step": "complete",
            "progress": 100,
            "result": result
        },
        "success"  # 消息级别，可选，默认info
    )


def generate_error_message(func, exception):
    """生成函数执行异常的推送消息"""
    return (
        "agent_progress",
        "处理失败",
        {
            "step": "error",
            "error_msg": str(exception)
        },
        "error"
    )


# 配置推送规则，业务代码零侵入
agent_push_config = PushConfig(
    enable_push=True,
    user_id_getter=get_user_id_from_args,
    push_on_start=True,
    push_on_end=True,
    push_on_error=True,
    start_message_generator=generate_start_message,
    end_message_generator=generate_end_message,
    error_message_generator=generate_error_message,
    persist_messages=True
)


@trace(push_config=agent_push_config)
async def agent_execute(user_id: int, session_id: str, user_input: str):
    """
    Agent执行函数，内部不需要任何推送相关代码
    所有推送逻辑通过注解配置自动完成
    """
    # 模拟业务逻辑
    print(f"Agent处理用户{user_id}的请求: {user_input}")
    await asyncio.sleep(2)  # 模拟耗时操作

    # 模拟异常情况
    # if "error" in user_input:
    #     raise Exception("处理过程中发生错误")

    return {"answer": "这是AI的回答内容", "usage": 100}


# ==============================
# 示例2：视频处理任务推送
# ==============================

def get_video_task_user_id(func, *args, **kwargs):
    """从视频任务参数中提取用户ID"""
    task = kwargs.get("task") or args[0]
    return task["user_id"]


video_task_push_config = PushConfig(
    enable_push=True,
    user_id_getter=get_video_task_user_id,
    push_on_start=False,  # 不需要推送开始消息
    push_on_end=True,
    push_on_error=True,
    end_message_generator=lambda f, result: (
        "task_status",
        "视频生成完成",
        {"task_id": result["task_id"], "video_url": result["url"]},
        "success"
    ),
    error_message_generator=lambda f, e: (
        "task_status",
        "视频生成失败",
        {"error": str(e)},
        "error"
    )
)


@trace(push_config=video_task_push_config)
async def process_video_task(task: dict):
    """视频处理任务，自动推送完成/失败状态"""
    print(f"处理视频任务: {task['task_id']}")
    await asyncio.sleep(3)

    return {
        "task_id": task["task_id"],
        "url": f"/videos/{task['task_id']}.mp4",
        "duration": 15.5
    }


# ==============================
# 示例3：极简配置方式
# ==============================

simple_push_config = PushConfig(
    enable_push=True,
    user_id_getter=lambda *args, **kwargs: kwargs["user_id"],
    push_on_end=True,
    end_message_generator=lambda f, r: ("notification", "操作成功", {"result": r})
)


@trace(push_config=simple_push_config)
async def some_operation(user_id: int, data: dict):
    """简单操作，只需要推送结果"""
    await asyncio.sleep(1)
    return {"status": "success", "data": data}


# ==============================
# 运行示例
# ==============================

async def main():
    print("=== 示例1：Agent执行推送 ===")
    await agent_execute(
        user_id=1,
        session_id="session_123456",
        user_input="帮我写一个带货文案"
    )

    print("\n=== 示例2：视频任务推送 ===")
    await process_video_task({
        "user_id": 1,
        "task_id": 1001,
        "video_path": "/upload/input.mp4"
    })

    print("\n=== 示例3：简单操作推送 ===")
    await some_operation(
        user_id=1,
        data={"key": "value"}
    )

    print("\n所有示例执行完成，相关消息已自动推送给对应用户")


if __name__ == "__main__":
    asyncio.run(main())
