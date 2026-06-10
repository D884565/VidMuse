from pathlib import Path


def test_merge_service_does_not_spawn_background_tasks_with_asyncio_create_task():
    source = Path("backend/v1/app/merge/service/merge_service.py").read_text(encoding="utf-8")

    assert "asyncio.create_task(" not in source


def test_merge_service_marks_tasks_queued_for_persistent_worker_execution():
    source = Path("backend/v1/app/merge/service/merge_service.py").read_text(encoding="utf-8")

    assert 'status="queued"' in source
    assert "_execute_replace_audio" in source
    assert "send_task(" in source
    assert "task_id=task_id" in source
