"""任务调度模块测试用例"""
import pytest
from unittest.mock import patch, MagicMock
from backend.v1.app.task_scheduler.dto.task_schema import TaskSubmitRequest, TaskTypeEnum
from backend.v1.app.task_scheduler.service.task_service import task_service


@pytest.mark.asyncio
async def test_submit_task():
    """测试提交任务"""
    # Mock数据库会话
    mock_db = MagicMock()

    # Mock Celery send_task
    with patch('backend.v1.app.task_scheduler.service.task_service.celery_app.send_task') as mock_send_task:
        mock_task = MagicMock()
        mock_task.id = "test_task_id"
        mock_send_task.return_value = mock_task

        # Mock推送服务
        with patch('backend.v1.app.task_scheduler.service.task_service.push_service.push_message') as mock_push:
            mock_push.return_value = True

            # 构造请求
            request = TaskSubmitRequest(
                task_type=TaskTypeEnum.VIDEO_PRODUCTION,
                payload={"param1": "value1"},
                user_id=123
            )

            # 调用服务
            result = await task_service.submit_task(mock_db, request)

            # 验证结果
            assert result["task_id"] == "test_task_id"
            assert result["status"] == "queued"
            assert "trace_id" in result
            assert len(result["trace_id"]) == 8

            # 验证Celery调用
            mock_send_task.assert_called_once()
            args, kwargs = mock_send_task.call_args
            assert args[0] == "video_production"
            assert kwargs["queue"] == "video_production"
            assert kwargs["kwargs"]["user_id"] == 123
            assert "trace_id" in kwargs["kwargs"]

            # 验证推送调用
            mock_push.assert_called_once()


@pytest.mark.asyncio
async def test_get_task_status():
    """测试查询任务状态"""
    # Mock AsyncResult
    with patch('backend.v1.app.task_scheduler.service.task_service.AsyncResult') as mock_async_result:
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.result = {"output": "test_result"}
        mock_async_result.return_value = mock_result

        # 调用服务
        status = await task_service.get_task_status("test_task_id")

        # 验证结果
        assert status is not None
        assert status.task_id == "test_task_id"
        assert status.status == "succeeded"
        assert status.result == {"output": "test_result"}


@pytest.mark.asyncio
async def test_cancel_task():
    """测试取消任务"""
    # Mock数据库会话
    mock_db = MagicMock()

    # Mock revoke方法
    with patch('backend.v1.app.task_scheduler.service.task_service.celery_app.control.revoke') as mock_revoke:
        # Mock推送服务
        with patch('backend.v1.app.task_scheduler.service.task_service.push_service.push_message') as mock_push:
            mock_push.return_value = True

            # 调用服务
            result = await task_service.cancel_task(mock_db, "test_task_id", user_id=123)

            # 验证结果
            assert result["success"] == True
            assert result["message"] == "任务已取消"

            # 验证revoke调用
            mock_revoke.assert_called_once_with("test_task_id", terminate=True)

            # 验证推送调用
            mock_push.assert_called_once()
