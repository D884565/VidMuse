from types import SimpleNamespace

import pytest

from backend.v1.app.generate.dao.project_dao import ProjectDAO


class FakeResult:
    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._value

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self):
        self.operations = []
        self.committed = False
        self.select_calls = 0

    async def execute(self, statement):
        sql = str(statement)
        self.operations.append(sql)
        if "SELECT projects.id" in sql:
            self.select_calls += 1
            return FakeResult(59)
        if "SELECT push_messages.message_id" in sql:
            return FakeResult(rows=[])
        return FakeResult(None, [])

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_project_delete_deletes_scripts_before_frames_to_handle_parent_links():
    db = FakeDB()

    ok = await ProjectDAO.delete(db, 59)

    assert ok is True
    assert db.committed is True

    scripts_delete = next(i for i, sql in enumerate(db.operations) if "DELETE FROM scripts" in sql)
    frames_delete = next(i for i, sql in enumerate(db.operations) if "DELETE FROM frames" in sql)

    assert scripts_delete < frames_delete


@pytest.mark.asyncio
async def test_project_delete_nulls_script_parent_links_before_deleting_scripts():
    db = FakeDB()

    await ProjectDAO.delete(db, 59)

    parent_null_update = next(
        i for i, sql in enumerate(db.operations)
        if "UPDATE scripts SET parent_id=:parent_id" in sql
    )
    scripts_delete = next(i for i, sql in enumerate(db.operations) if "DELETE FROM scripts" in sql)

    assert parent_null_update < scripts_delete
