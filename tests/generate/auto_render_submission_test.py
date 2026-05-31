from types import SimpleNamespace

import pytest

from backend.v1.app.generate.service.video_generation import VideoGenerationService


class FakeFrame:
    def __init__(self, sequence=1, status=0, image_url=None):
        self.sequence = sequence
        self.status = status
        self.image_url = image_url


class FakeProject:
    def __init__(self):
        self.id = 1
        self.status = "script_ready"
        self.workflow_stage = "script"
        self.stage_status = "awaiting_review"
        self.last_task_id = None


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class FakeProjectResult:
    def __init__(self, project):
        self.project = project

    def scalar_one_or_none(self):
        return self.project


class FakeFramesResult:
    def __init__(self, frames):
        self.frames = frames

    def scalars(self):
        return FakeScalarResult(self.frames)


class FakeDB:
    def __init__(self, project, frames):
        self.project = project
        self.frames = frames
        self.calls = 0

    async def execute(self, _query):
        self.calls += 1
        if self.calls == 1:
            return FakeProjectResult(self.project)
        return FakeFramesResult(self.frames)

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_submit_generation_task_allows_missing_images_for_auto_render(monkeypatch):
    service = VideoGenerationService()
    project = FakeProject()
    db = FakeDB(project, [FakeFrame()])

    async def fake_create_task(*args, **kwargs):
        return SimpleNamespace(id=99)

    async def fake_set_celery_task_id(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "backend.v1.app.generate.service.video_generation.generation_task_service.create_task",
        fake_create_task,
    )
    monkeypatch.setattr(
        "backend.v1.app.generate.service.video_generation.generation_task_service.set_celery_task_id",
        fake_set_celery_task_id,
    )
    monkeypatch.setattr(
        "backend.v1.app.generate.service.video_generation.celery_app.send_task",
        lambda *args, **kwargs: SimpleNamespace(id="celery-99"),
    )

    result = await service.submit_generation_task(
        db,
        1,
        require_ready_images=False,
        trigger_source="auto_render",
    )

    assert result["status"] == "render_queued"
    assert result["task_id"] == 99
    assert result["celery_task_id"] == "celery-99"
    assert project.status == "render_queued"


@pytest.mark.asyncio
async def test_submit_generation_task_still_blocks_manual_render_when_images_missing():
    service = VideoGenerationService()
    db = FakeDB(FakeProject(), [FakeFrame()])

    with pytest.raises(ValueError, match="未成功生成图片"):
        await service.submit_generation_task(
            db,
            1,
            require_ready_images=True,
            trigger_source="manual_render",
        )
