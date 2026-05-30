"""Shared limits for generation workflow timing."""

from decimal import Decimal
from typing import Iterable

MIN_TARGET_DURATION_SECONDS = 12
MAX_TARGET_DURATION_SECONDS = 20
DEFAULT_TARGET_DURATION_SECONDS = 15


def normalize_target_duration(value: int | float | Decimal | None) -> int:
    """Clamp a requested project target duration to the supported production range."""
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
    """Ensure edited frame durations do not exceed the normalized project target duration."""
    limit = normalize_target_duration(target_duration)
    total_duration = sum(float(duration or 0) for duration in frame_durations)
    if total_duration > limit:
        raise ValueError(f"frame total duration cannot exceed project target duration: {limit} seconds")
    return total_duration
