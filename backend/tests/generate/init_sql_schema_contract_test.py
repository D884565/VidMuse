from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read_init_sql() -> str:
    return (ROOT / "resources/init.sql").read_text(encoding="utf-8").lower()


def test_init_sql_contains_generation_task_progress_schema():
    source = read_init_sql()

    assert "create table if not exists generation_tasks" in source
    for column in (
        "progress",
        "current_step",
        "current_frame_id",
        "retry_count",
        "error_code",
        "trace_id",
        "started_at",
        "finished_at",
    ):
        assert column in source

    assert "create table if not exists generation_task_steps" in source
    for column in (
        "task_id",
        "step_name",
        "frame_id",
        "input_snapshot",
        "output_snapshot",
        "finished_at",
    ):
        assert column in source


def test_init_sql_contains_project_asset_binding_schema():
    source = read_init_sql()

    assert "create table if not exists project_assets" in source
    assert "uq_project_assets_project_asset_role" in source
    assert "scope" in source
    assert "metadata" in source
    assert "tags" in source


def test_init_sql_contains_editable_script_version_schema():
    source = read_init_sql()

    assert "create table if not exists scripts" in source
    assert "parent_id" in source
    assert "foreign key (parent_id) references scripts(id)" in source
