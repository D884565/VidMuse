from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from backend.v1.app.push.service.task_event_service import task_event_service


def test_task_event_service_builds_snapshot_from_rows():
    rows = [
        SimpleNamespace(
            task_id="gen_1",
            task_domain="generation",
            task_type="render",
            event_type="task_created",
            status="queued",
            progress=0,
            project_id=42,
            asset_id=None,
            trace_id="trace_1",
            celery_task_id=None,
            content={"task_id": "gen_1", "status": "queued"},
            created_at=datetime(2026, 6, 6, 12, 0, 0),
        )
    ]

    events = task_event_service.events_from_rows(rows)
    snapshot = task_event_service.aggregate_snapshot(events)

    assert snapshot["task_id"] == "gen_1"
    assert snapshot["project_id"] == 42
    assert snapshot["status"] == "queued"
    assert snapshot["created_at"] == "2026-06-06T12:00:00"


def test_removed_task_tables_are_not_imported_by_runtime_services():
    runtime_files = [
        "backend/v1/app/merge/service/merge_service.py",
        "backend/v1/app/generate/service/generateUtils/task_service.py",
        "backend/v1/app/models/__init__.py",
    ]

    for path in runtime_files:
        source = Path(path).read_text(encoding="utf-8")
        assert "MergeTask" not in source
        assert "GenerationTaskStep" not in source
