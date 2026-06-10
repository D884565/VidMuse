"""生成工作流时长限制的共享配置。"""

from decimal import Decimal
from typing import Iterable

MIN_TARGET_DURATION_SECONDS = 10
MAX_TARGET_DURATION_SECONDS = 25
DEFAULT_TARGET_DURATION_SECONDS = 15


def normalize_target_duration(value: int | float | Decimal | None) -> int:
    """将请求的项目目标时长限制在支持的生产范围内。"""
    if value is None:
        duration = DEFAULT_TARGET_DURATION_SECONDS
    else:
        duration = int(value)
    return max(MIN_TARGET_DURATION_SECONDS, min(MAX_TARGET_DURATION_SECONDS, duration))


def validate_total_frame_duration(
    frame_durations: Iterable[int | float | Decimal | None],
    *,
    target_duration: int | float | Decimal | None,
) -> float:
    """确保编辑后的分镜时长不超过规范化后的项目目标时长。"""
    limit = normalize_target_duration(target_duration)
    total_duration = sum(float(duration or 0) for duration in frame_durations)
    if total_duration > limit:
        raise ValueError(f"frame total duration cannot exceed project target duration: {limit} seconds")
    return total_duration
