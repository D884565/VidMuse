from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read_init_sql() -> str:
    return (ROOT / "resources/init.sql").read_text(encoding="utf-8").lower()


def test_init_sql_contains_new_generation_tasks_columns():
    source = read_init_sql()

    assert "create table if not exists generation_tasks" in source
    for column in (
        "task_id varchar(80)",
        "current_stage varchar(50)",
        "trigger_source varchar(50)",
        "started_at datetime",
        "finished_at datetime",
        "index idx_task_id (task_id)",
    ):
        assert column in source
