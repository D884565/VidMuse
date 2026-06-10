import pytest

from backend.v1.app.generate.service.workflow.limits import (
    DEFAULT_TARGET_DURATION_SECONDS,
    MAX_TARGET_DURATION_SECONDS,
    MIN_TARGET_DURATION_SECONDS,
    normalize_target_duration,
    validate_total_frame_duration,
)


def test_normalize_target_duration_uses_shared_bounds():
    assert normalize_target_duration(None) == DEFAULT_TARGET_DURATION_SECONDS
    assert normalize_target_duration(3) == MIN_TARGET_DURATION_SECONDS
    assert normalize_target_duration(99) == MAX_TARGET_DURATION_SECONDS
    assert normalize_target_duration(18) == 18


def test_validate_total_frame_duration_uses_project_target_duration_not_fixed_15_seconds():
    validate_total_frame_duration([8, 8], target_duration=20)

    with pytest.raises(ValueError, match="20"):
        validate_total_frame_duration([10, 11], target_duration=20)
