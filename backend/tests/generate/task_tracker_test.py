import pytest
from unittest.mock import MagicMock, patch

from backend.v1.app.generate.service.generateUtils.task_tracker import GenerationTaskTracker


@pytest.fixture
def tracker():
    return GenerationTaskTracker()


@pytest.fixture
def mock_db():
    return MagicMock()


def test_create_task(tracker, mock_db):
    """测试创建任务。"""
    with patch("backend.v1.app.generate.service.generateUtils.task_tracker.task_tracker_dao") as mock_dao:
        mock_task = MagicMock()
        mock_task.task_id = "gen_test123"
        mock_dao.create_task.return_value = mock_task

        task_id = tracker.create_task(mock_db, 1, "image", "manual")

        assert task_id == "gen_test123"
        mock_dao.create_task.assert_called_once_with(mock_db, 1, "image", "manual", None)


def test_get_pending_frames(tracker, mock_db):
    """测试获取待处理帧。"""
    with patch("backend.v1.app.generate.service.generateUtils.task_tracker.task_tracker_dao") as mock_dao:
        mock_dao.get_pending_frames.return_value = [1, 2, 3]

        result = tracker.get_pending_frames(mock_db, "gen_test123", "image")

        assert result == [1, 2, 3]


def test_get_failed_frames(tracker, mock_db):
    """测试获取失败帧。"""
    with patch("backend.v1.app.generate.service.generateUtils.task_tracker.task_tracker_dao") as mock_dao:
        mock_dao.get_failed_frames.return_value = [2, 5]

        result = tracker.get_failed_frames(mock_db, "gen_test123", "image")

        assert result == [2, 5]


def test_get_frame_summary(tracker, mock_db):
    """测试获取帧状态汇总。"""
    with patch("backend.v1.app.generate.service.generateUtils.task_tracker.task_tracker_dao") as mock_dao:
        mock_dao.get_frame_summary.return_value = {
            "total": 6,
            "pending": 1,
            "running": 0,
            "succeeded": 4,
            "failed": 1,
        }

        result = tracker.get_frame_summary(mock_db, "gen_test123", "image")

        assert result["total"] == 6
        assert result["failed"] == 1
