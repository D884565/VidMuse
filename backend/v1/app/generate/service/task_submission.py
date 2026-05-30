"""任务提交幂等辅助函数。"""

RUNNING_TASK_STATUSES = {"queued", "running"}


def has_running_stage_task(tasks, task_type: str) -> bool:
    return any(
        getattr(task, "task_type", None) == task_type
        and getattr(task, "status", None) in RUNNING_TASK_STATUSES
        for task in tasks
    )
