from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read_init_sql() -> str:
    return (ROOT / "resources/init.sql").read_text(encoding="utf-8").lower()


def test_init_sql_uses_push_task_tracking_instead_of_old_task_tables():
    source = read_init_sql()

    assert "create table if not exists push_messages" in source
    for column in (
        "business_type",
        "task_id",
        "task_domain",
        "task_type",
        "project_id",
        "asset_id",
        "event_type",
        "status",
        "progress",
        "trace_id",
    ):
        assert column in source

    assert "create table if not exists merge_tasks" not in source
    assert "create table if not exists generation_task_steps" not in source
    assert "create table if not exists generation_tasks_steps" not in source


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
