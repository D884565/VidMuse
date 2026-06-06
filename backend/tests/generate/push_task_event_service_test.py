from datetime import datetime

from backend.v1.app.push.dao.message_dao import message_dao
from backend.v1.app.push.dto.message_schema import PushMessageCreate
from backend.v1.app.push.service.task_event_service import TaskEvent, task_event_service


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1

    def refresh(self, row):
        row.created_at = datetime(2026, 6, 6, 12, 0, 0)
        self.refreshed.append(row)


def test_push_message_persists_task_metadata_columns():
    db = FakeSession()
    message = PushMessageCreate(
        user_id=7,
        message_type="task_event",
        title="Task created",
        content={"task_id": "gen_abc", "status": "queued"},
        level="info",
        trace_id="trace_1",
        business_type="task",
        task_id="gen_abc",
        task_domain="generation",
        task_type="render",
        project_id=42,
        asset_id=None,
        event_type="task_created",
        status="queued",
        progress=0,
    )

    row = message_dao.create_message(db, message, "msg_1")

    assert row.message_id == "msg_1"
    assert row.business_type == "task"
    assert row.task_id == "gen_abc"
    assert row.task_domain == "generation"
    assert row.task_type == "render"
    assert row.project_id == 42
    assert row.event_type == "task_created"
    assert row.status == "queued"
    assert row.progress == 0
    assert db.commits == 1


def test_task_snapshot_uses_latest_status_and_terminal_timestamps():
    events = [
        TaskEvent(
            task_id="gen_1",
            task_domain="generation",
            task_type="render",
            event_type="task_created",
            status="queued",
            progress=0,
            project_id=42,
            user_id=7,
            trace_id="t1",
            created_at="2026-06-06T12:00:00",
        ),
        TaskEvent(
            task_id="gen_1",
            task_domain="generation",
            task_type="render",
            event_type="task_started",
            status="running",
            progress=10,
            current_step="PROJECT_VALIDATION",
            project_id=42,
            user_id=7,
            trace_id="t1",
            created_at="2026-06-06T12:01:00",
        ),
        TaskEvent(
            task_id="gen_1",
            task_domain="generation",
            task_type="render",
            event_type="task_succeeded",
            status="succeeded",
            progress=100,
            current_step="COMPLETED",
            project_id=42,
            user_id=7,
            trace_id="t1",
            result={"video_url": "https://cdn.test/final.mp4"},
            created_at="2026-06-06T12:05:00",
        ),
    ]

    snapshot = task_event_service.aggregate_snapshot(events)

    assert snapshot["task_id"] == "gen_1"
    assert snapshot["status"] == "succeeded"
    assert snapshot["progress"] == 100
    assert snapshot["current_step"] == "COMPLETED"
    assert snapshot["created_at"] == "2026-06-06T12:00:00"
    assert snapshot["started_at"] == "2026-06-06T12:01:00"
    assert snapshot["finished_at"] == "2026-06-06T12:05:00"
    assert snapshot["result"] == {"video_url": "https://cdn.test/final.mp4"}


def test_task_steps_group_by_step_key_and_frame_id():
    events = [
        TaskEvent(
            task_id="gen_1",
            task_domain="generation",
            task_type="render",
            event_type="step_started",
            status="running",
            progress=30,
            current_step="IMAGE_GENERATING",
            project_id=42,
            user_id=7,
            trace_id="t1",
            step={
                "step_key": "IMAGE_GENERATING",
                "frame_id": 9,
                "status": "running",
                "progress": 30,
            },
            created_at="2026-06-06T12:02:00",
        ),
        TaskEvent(
            task_id="gen_1",
            task_domain="generation",
            task_type="render",
            event_type="step_finished",
            status="running",
            progress=45,
            current_step="IMAGE_GENERATING",
            project_id=42,
            user_id=7,
            trace_id="t1",
            step={
                "step_key": "IMAGE_GENERATING",
                "frame_id": 9,
                "status": "succeeded",
                "progress": 45,
                "output_snapshot": {"image_url": "u"},
            },
            created_at="2026-06-06T12:03:00",
        ),
    ]

    steps = task_event_service.aggregate_steps(events)

    assert steps == [
        {
            "step_name": "IMAGE_GENERATING",
            "frame_id": 9,
            "status": "succeeded",
            "progress": 45,
            "input_snapshot": None,
            "output_snapshot": {"image_url": "u"},
            "error_message": None,
            "started_at": "2026-06-06T12:02:00",
            "finished_at": "2026-06-06T12:03:00",
        }
    ]


def test_emit_event_sync_persists_task_event_metadata():
    db = FakeSession()

    task_event_service.emit_event_sync(
        db=db,
        task_id="gen_abc",
        task_domain="generation",
        task_type="render",
        event_type="task_started",
        status="running",
        progress=10,
        project_id=42,
        trace_id="trace_1",
        current_step="PROJECT_VALIDATION",
    )

    row = db.added[0]
    assert row.message_type == "task_event"
    assert row.task_id == "gen_abc"
    assert row.event_type == "task_started"
    assert row.status == "running"
    assert row.progress == 10
    assert row.content["current_step"] == "PROJECT_VALIDATION"
