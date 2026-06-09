from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.v1.app.generate.service.chat.chat_service import ChatService
from backend.v1.app.generate.service.stages.video_workflow import VideoGenerationService


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
async def test_submit_generation_task_allows_script_review_for_chat_semantic_edit(monkeypatch):
    service = VideoGenerationService()
    project = SimpleNamespace(
        id=1,
        status="script_ready",
        workflow_stage="script",
        stage_status="awaiting_review",
        last_task_id=None,
    )
    db = FakeDB(project, [SimpleNamespace(sequence=1, status=0, image_url=None)])

    async def fake_create_task(*args, **kwargs):
        return SimpleNamespace(id="gen_100")

    async def fake_set_celery_task_id(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "backend.v1.app.generate.service.stages.video_workflow.generation_task_service.create_task",
        fake_create_task,
    )
    monkeypatch.setattr(
        "backend.v1.app.generate.service.stages.video_workflow.generation_task_service.set_celery_task_id",
        fake_set_celery_task_id,
    )
    monkeypatch.setattr(
        "backend.v1.app.generate.service.stages.video_workflow.celery_app.send_task",
        lambda *args, **kwargs: SimpleNamespace(id="celery-100"),
    )

    result = await service.submit_generation_task(
        db,
        1,
        require_ready_images=False,
        trigger_source="chat_semantic_edit",
    )

    assert result["status"] == "render_queued"
    assert result["task_id"] == "gen_100"
    assert result["celery_task_id"] == "celery-100"


@pytest.mark.asyncio
async def test_confirm_and_advance_returns_image_running_state_to_chat_done_event():
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    project = SimpleNamespace(
        id=1,
        workflow_stage="script",
        stage_status="awaiting_review",
        dirty_stage=None,
        last_task_id="script_1",
        status="script_ready",
        script_confirmed_at=None,
        images_confirmed_at=None,
        video_confirmed_at=None,
    )

    with patch(
        "backend.v1.app.generate.service.chat.chat_service.image_workflow_service.submit_image_task",
        new=AsyncMock(return_value={"task_id": "image_1", "status": "running"}),
    ):
        task_result, blocks = await service._handle_confirm_and_advance(mock_db, project, 1)

    assert task_result["task_id"] == "image_1"
    assert project.workflow_stage == "image"
    assert project.stage_status == "running"
    assert project.last_task_id == "image_1"
    assert any(block.get("stage") == "image" and block.get("status") == "running" for block in blocks)


@pytest.mark.asyncio
async def test_chat_edit_frame_with_image_change_submits_single_frame_image_regeneration():
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    frame = SimpleNamespace(
        id=1,
        project_id=1,
        sequence=1,
        description="一个男生手持产品展示",
        image_prompt="一个男生手持产品展示",
        video_prompt=None,
        narration=None,
        image_url="https://cdn.test/old.png",
        video_url="https://cdn.test/old.mp4",
        audio_url=None,
        status=2,
        dirty=0,
        duration=3.0,
        ai_params={},
        error_message=None,
        metadata_=None,
        version=1,
        last_edited_at=None,
    )
    project = SimpleNamespace(
        id=1,
        workflow_stage="video",
        stage_status="awaiting_review",
        dirty_stage=None,
        last_task_id=None,
        status="review_required",
        script_confirmed_at="2026-01-01",
        images_confirmed_at="2026-01-01",
        video_confirmed_at="2026-01-01",
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [frame]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch.object(
        service,
        "_submit_frame_image_regeneration_tasks",
        new=AsyncMock(return_value=([{"frame_id": 1, "sequence": 1}], {"task_id": "frame_image_1", "status": "queued"})),
    ) as mock_submit:
        task_result, updated, blocks = await service._handle_edit_frame(
            mock_db,
            project,
            [1],
            {"description": {"replace": ["男生", "女生"]}},
        )

    assert task_result["task_id"] == "frame_image_1"
    assert updated == [{"frame_id": 1, "sequence": 1}]
    assert frame.description == "一个女生手持产品展示"
    mock_submit.assert_awaited_once()
    assert mock_submit.await_args.args[:3] == (mock_db, project, [1])
    assert any(block.get("type") == "progress_card" and block.get("stage") == "image" for block in blocks)


@pytest.mark.asyncio
async def test_chat_price_edit_submits_single_frame_image_regeneration():
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    frame = SimpleNamespace(
        id=1,
        project_id=1,
        sequence=4,
        description="保温杯放在左侧，右侧是醒目的39.9元价格牌",
        image_prompt="保温杯放在左侧，右侧是醒目的39.9元价格牌",
        video_prompt="镜头快速推近到39.9元价格牌上",
        narration="现在下单只要39.9，抢！",
        image_url="https://cdn.test/old.png",
        video_url="https://cdn.test/old.mp4",
        audio_url=None,
        status=2,
        dirty=0,
        duration=3.0,
        ai_params={},
        error_message=None,
        metadata_=None,
        version=1,
        last_edited_at=None,
    )
    project = SimpleNamespace(
        id=1,
        workflow_stage="video",
        stage_status="awaiting_review",
        dirty_stage=None,
        last_task_id=None,
        status="review_required",
        script_confirmed_at="2026-01-01",
        images_confirmed_at="2026-01-01",
        video_confirmed_at="2026-01-01",
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [frame]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch.object(
        service,
        "_submit_frame_image_regeneration_tasks",
        new=AsyncMock(return_value=([{"frame_id": 1, "sequence": 4}], {"task_id": "frame_image_4", "status": "queued"})),
    ) as mock_submit:
        task_result, updated, blocks = await service._handle_edit_frame(
            mock_db,
            project,
            [1],
            {"price": "99元"},
        )

    assert task_result["task_id"] == "frame_image_4"
    assert updated == [{"frame_id": 1, "sequence": 4}]
    assert "99元" in frame.description
    assert "99元" in frame.image_prompt
    mock_submit.assert_awaited_once()
    assert any(block.get("type") == "progress_card" and block.get("stage") == "image" for block in blocks)


@pytest.mark.asyncio
async def test_chat_edit_frame_during_script_review_keeps_script_reviewable():
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    frame = SimpleNamespace(
        id=1,
        project_id=1,
        sequence=1,
        description="old scene",
        image_prompt="old scene",
        video_prompt="old motion",
        narration="old narration",
        image_url=None,
        video_url=None,
        audio_url=None,
        status=0,
        dirty=0,
        duration=4.0,
        ai_params={},
        error_message=None,
        metadata_=None,
        version=1,
        last_edited_at=None,
    )
    project = SimpleNamespace(
        id=1,
        workflow_stage="script",
        stage_status="awaiting_review",
        dirty_stage=None,
        last_task_id="script_1",
        status="script_ready",
        script_confirmed_at=None,
        images_confirmed_at=None,
        video_confirmed_at=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [frame]
    mock_db.execute = AsyncMock(return_value=mock_result)

    task_result, updated, blocks = await service._handle_edit_frame(
        mock_db,
        project,
        [1],
        {"description": "new scene"},
    )

    assert task_result is None
    assert updated == [{"frame_id": 1, "sequence": 1}]
    assert frame.description == "new scene"
    assert project.workflow_stage == "script"
    assert project.stage_status == "awaiting_review"
    assert project.dirty_stage is None
    assert any(block.get("type") == "frame_editor" for block in blocks)


@pytest.mark.asyncio
async def test_image_affecting_edit_during_script_review_does_not_start_render_task():
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    frame = SimpleNamespace(
        id=1,
        project_id=1,
        sequence=1,
        description="old visual",
        image_prompt="old visual",
        video_prompt="old motion",
        narration="old narration",
        image_url=None,
        video_url=None,
        audio_url=None,
        status=0,
        dirty=0,
        duration=4.0,
        ai_params={},
        error_message=None,
        metadata_=None,
        version=1,
        last_edited_at=None,
    )
    project = SimpleNamespace(
        id=1,
        workflow_stage="script",
        stage_status="awaiting_review",
        dirty_stage=None,
        last_task_id="script_1",
        status="script_ready",
        script_confirmed_at=None,
        images_confirmed_at=None,
        video_confirmed_at=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [frame]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "backend.v1.app.generate.service.chat.chat_service.video_generation_service.submit_generation_task",
        new=AsyncMock(return_value={"task_id": "render_1", "status": "render_queued"}),
    ) as mock_submit:
        task_result, updated, blocks = await service._handle_edit_frame(
            mock_db,
            project,
            [1],
            {"description": {"replace": ["old", "new"]}},
        )

    assert task_result is None
    assert updated == [{"frame_id": 1, "sequence": 1}]
    assert frame.description == "new visual"
    assert project.workflow_stage == "script"
    assert project.stage_status == "awaiting_review"
    mock_submit.assert_not_awaited()
    assert not any(block.get("type") == "progress_card" for block in blocks)


@pytest.mark.asyncio
async def test_chat_narration_only_edit_submits_render_task_and_returns_task_result():
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    frame = SimpleNamespace(
        id=1,
        project_id=1,
        sequence=1,
        description="女生展示水杯",
        image_prompt="女生展示水杯",
        video_prompt="镜头推进",
        narration="旧旁白",
        image_url="https://cdn.test/frame.png",
        video_url="https://cdn.test/frame.mp4",
        audio_url=None,
        status=2,
        dirty=0,
        duration=3.0,
        ai_params={},
        error_message=None,
        metadata_=None,
        version=1,
        last_edited_at=None,
    )
    project = SimpleNamespace(
        id=1,
        workflow_stage="completed",
        stage_status="awaiting_review",
        dirty_stage=None,
        last_task_id=None,
        status="completed",
        script_confirmed_at="2026-01-01",
        images_confirmed_at="2026-01-01",
        video_confirmed_at="2026-01-01",
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [frame]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "backend.v1.app.generate.service.chat.chat_service.video_generation_service.submit_generation_task",
        new=AsyncMock(return_value={"task_id": "render_1", "status": "render_queued"}),
    ) as mock_submit:
        task_result, updated, blocks = await service._handle_edit_frame(
            mock_db,
            project,
            [1],
            {"narration": "新旁白"},
        )

    assert task_result["task_id"] == "render_1"
    assert updated == [{"frame_id": 1, "sequence": 1}]
    assert frame.narration == "新旁白"
    assert frame.ai_params["tts_dirty"] is True
    mock_submit.assert_awaited_once_with(
        mock_db,
        project.id,
        require_ready_images=True,
        trigger_source="chat_narration_edit",
    )
    assert any(block.get("type") == "progress_card" and block.get("stage") == "video" for block in blocks)


@pytest.mark.asyncio
async def test_regenerate_video_only_keeps_image_stage_confirmed_before_render_submission():
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    frame = SimpleNamespace(
        id=1,
        project_id=1,
        sequence=1,
        image_url="https://cdn.test/frame.png",
        video_url="https://cdn.test/frame.mp4",
        status=2,
        dirty=0,
    )
    project = SimpleNamespace(
        id=1,
        workflow_stage="video",
        stage_status="awaiting_review",
        dirty_stage=None,
        last_task_id="video_1",
        status="review_required",
        script_confirmed_at="2026-01-01",
        images_confirmed_at="2026-01-01",
        video_confirmed_at="2026-01-01",
    )

    with patch.object(service, "_get_frames", new=AsyncMock(return_value=[frame])):
        with patch(
            "backend.v1.app.generate.service.chat.chat_service.video_generation_service.submit_generation_task",
            new=AsyncMock(return_value={"task_id": "render_2", "status": "render_queued"}),
        ) as mock_submit:
            task_result = await service._submit_project_regeneration(
                mock_db,
                project,
                project.id,
                "REGENERATE_VIDEO_ONLY",
            )

    assert task_result["task_id"] == "render_2"
    assert frame.video_url is None
    assert frame.dirty == 1
    assert project.workflow_stage == "image"
    assert project.stage_status == "confirmed"
    assert project.dirty_stage == "video"
    mock_submit.assert_awaited_once_with(
        mock_db,
        project.id,
        require_ready_images=True,
        trigger_source="chat_regenerate_video_only",
    )
