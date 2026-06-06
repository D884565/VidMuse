import pytest
from unittest.mock import MagicMock, patch

from backend.v1.app.generate.service.generateUtils.retry_coordinator import RetryCoordinator, ResumePoint


@pytest.fixture
def coordinator():
    return RetryCoordinator()


@pytest.fixture
def mock_db():
    return MagicMock()


def test_determine_resume_point_no_task(coordinator, mock_db):
    """测试没有任务时的恢复点。"""
    with patch("backend.v1.app.generate.service.generateUtils.retry_coordinator.generation_task_tracker") as mock_tracker:
        mock_tracker.get_latest_task.return_value = None

        result = coordinator.determine_resume_point(mock_db, 1)

        assert result.stage == "start"
        assert result.task_id is None
        assert result.frames_to_retry == []


def test_determine_resume_point_failed_image(coordinator, mock_db):
    """测试图片阶段失败的恢复点。"""
    with patch("backend.v1.app.generate.service.generateUtils.retry_coordinator.generation_task_tracker") as mock_tracker:
        mock_tracker.get_latest_task.return_value = {
            "task_id": "gen_test123",
            "status": "failed",
            "current_stage": "image",
        }
        mock_tracker.get_failed_frames.return_value = [2, 3]

        result = coordinator.determine_resume_point(mock_db, 1)

        assert result.stage == "image"
        assert result.task_id == "gen_test123"
        assert result.frames_to_retry == [2, 3]


def test_prepare_retry_with_frame_ids(coordinator, mock_db):
    """测试指定帧ID的重试准备。"""
    with patch("backend.v1.app.generate.service.generateUtils.retry_coordinator.generation_task_tracker") as mock_tracker:
        mock_tracker.create_task.return_value = "gen_new123"

        task_id, frames = coordinator.prepare_retry(mock_db, 1, stage="image", frame_ids=[2, 3])

        assert task_id == "gen_new123"
        assert frames == [2, 3]
