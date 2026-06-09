from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.dialects import mysql

from backend.v1.app.generate.dao.task_tracker_dao import TaskTrackerDAO


def test_init_frame_progress_uses_mysql_upsert():
    dao = TaskTrackerDAO()
    db = MagicMock()

    dao.init_frame_progress(
        db,
        task_id="gen_test123",
        project_id=1,
        frame_ids=[10, 11],
        stage="image",
    )

    assert db.add.call_count == 0
    assert db.execute.call_count == 1
    assert db.flush.call_count == 1

    statement = db.execute.call_args.args[0]
    compiled = str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "INSERT INTO generation_frame_progress" in compiled
    assert "ON DUPLICATE KEY UPDATE" in compiled


def test_create_task_reuses_existing_explicit_task_id(monkeypatch):
    dao = TaskTrackerDAO()
    db = MagicMock()
    existing = SimpleNamespace(task_id="gen_existing")

    monkeypatch.setattr(dao, "get_task", lambda _db, task_id: existing if task_id == "gen_existing" else None)

    task = dao.create_task(db, 51, "render", task_id="gen_existing")

    assert task is existing
    assert db.add.call_count == 0
    assert db.flush.call_count == 0
