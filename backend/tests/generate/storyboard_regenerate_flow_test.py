"""分镜编辑 → 重新生成图片 → 重新生成视频 全链路测试

覆盖路径：
1. 用户修改分镜描述 → image_prompt 同步更新
2. 重新生成图片 → 状态重置、指令存入 ai_params、Celery 任务提交
3. 重新生成视频 → 工作流失效、dirty 标记、Celery 任务提交
4. 控制器异常处理 → 所有异常都转换为 BusinessException
5. 任务失败重试 → retry_count 正确持久化
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.v1.app.generate.service.chat.chat_service import ChatService, apply_frame_modifications


# ── helpers ──────────────────────────────────────────────────────────────────

class FakeFrame:
    """模拟 ORM Frame 对象"""
    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.project_id = kw.get("project_id", 1)
        self.sequence = kw.get("sequence", 1)
        self.description = kw.get("description", "商品在桌面上")
        self.image_prompt = kw.get("image_prompt", "商品在桌面上")
        self.video_prompt = kw.get("video_prompt", None)
        self.narration = kw.get("narration", None)
        self.image_url = kw.get("image_url", "https://cdn.test/1.png")
        self.video_url = kw.get("video_url", None)
        self.audio_url = kw.get("audio_url", None)
        self.status = kw.get("status", 2)
        self.dirty = kw.get("dirty", 0)
        self.duration = kw.get("duration", 3.0)
        self.ai_params = kw.get("ai_params", {})
        self.error_message = kw.get("error_message", None)
        self.metadata_ = kw.get("metadata_", None)


class FakeProject:
    """模拟 ORM Project 对象"""
    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.workflow_stage = kw.get("workflow_stage", "image")
        self.stage_status = kw.get("stage_status", "awaiting_review")
        self.dirty_stage = kw.get("dirty_stage", None)
        self.script_confirmed_at = kw.get("script_confirmed_at", "2026-01-01")
        self.images_confirmed_at = kw.get("images_confirmed_at", "2026-01-01")
        self.video_confirmed_at = kw.get("video_confirmed_at", None)


# ── 1. 分镜描述修改 → image_prompt 同步 ─────────────────────────────────────

def test_edit_frame_description_syncs_image_prompt():
    """修改分镜描述后 image_prompt 应同步更新"""
    frame = FakeFrame(description="原始描述", image_prompt="原始描述")
    apply_frame_modifications(frame, {"description": "展示商品特写，背景虚化"})

    assert frame.description == "展示商品特写，背景虚化"
    assert frame.image_prompt == "展示商品特写，背景虚化"


def test_edit_frame_narration_does_not_overwrite_image_prompt():
    """修改旁白不应覆盖 image_prompt"""
    frame = FakeFrame(description="原始描述", image_prompt="原始描述", narration="原始旁白")
    apply_frame_modifications(frame, {"narration": "新的旁白内容"})

    assert frame.narration == "新的旁白内容"
    assert frame.image_prompt == "原始描述"  # 未被覆盖


# ── 2. 重新生成图片 → 状态重置 + 指令存储 ────────────────────────────────────

@pytest.mark.asyncio
async def test_regenerate_frame_image_resets_state_and_stores_instruction():
    """重新生成图片应：清空 image_url、重置 status=0、设 dirty=1、存入指令"""
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    frame = FakeFrame(status=2, image_url="https://cdn.test/old.png", ai_params={})
    project = FakeProject()

    service._get_frame = AsyncMock(return_value=frame)
    service._get_project = AsyncMock(return_value=project)

    # Mock _mark_frames_for_image_regeneration 内部的 db.execute
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [frame]
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await service.regenerate_frame_image(mock_db, 1, 1, "换个角度拍摄")

    assert frame.image_url is None
    assert frame.status == 0
    assert frame.dirty == 1
    assert frame.ai_params["image_revision_instruction"] == "换个角度拍摄"
    assert result["status"] == "image_pending_regenerate"


@pytest.mark.asyncio
async def test_regenerate_frame_image_default_instruction():
    """无指令时使用默认文案"""
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    frame = FakeFrame(status=2, ai_params={})
    project = FakeProject()

    service._get_frame = AsyncMock(return_value=frame)
    service._get_project = AsyncMock(return_value=project)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [frame]
    mock_db.execute = AsyncMock(return_value=mock_result)

    await service.regenerate_frame_image(mock_db, 1, 1, None)

    assert frame.ai_params["image_revision_instruction"] == "重生成这张图片"


# ── 3. 重新生成剧本 → 状态重置 + 工作流失效 ──────────────────────────────────

@pytest.mark.asyncio
async def test_regenerate_frame_script_resets_status_and_invalidates_workflow():
    """重新生成剧本应：重置 status=0、设 dirty=1、附加指令到 description"""
    service = ChatService()
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    frame = FakeFrame(status=2, description="原始描述")
    project = FakeProject(workflow_stage="image", stage_status="awaiting_review")

    service._get_frame = AsyncMock(return_value=frame)
    service._get_project = AsyncMock(return_value=project)

    with patch("backend.v1.app.generate.service.chat.chat_service.generation_workflow_service") as mock_wf:
        result = await service.regenerate_frame(mock_db, 1, 1, "改为俯视角度")

    assert frame.status == 0
    assert frame.dirty == 1
    assert "改为俯视角度" in frame.description
    mock_wf.invalidate_from.assert_called_once_with(project, "script")
    assert result["status"] == "script_updated"


# ── 4. 控制器异常处理 → 鉴权在 try-catch 内 ──────────────────────────────────

def test_controller_regenerate_image_auth_inside_try_block():
    """验证 regenerate-image 端点的鉴权代码在 try 块内"""
    import inspect
    from backend.v1.app.generate.controller.generation import regenerate_frame_image

    source = inspect.getsource(regenerate_frame_image)

    # 找到 try 和 ProjectService.get_project 的位置
    try_pos = source.index("try:")
    get_project_pos = source.index("ProjectService.get_project")

    # get_project 应该在 try 之后（在 try 块内）
    assert get_project_pos > try_pos, \
        "ProjectService.get_project 应该在 try 块内，否则非 BusinessException 会逃逸"


def test_controller_regenerate_video_auth_inside_try_block():
    """验证 regenerate-video 端点的鉴权代码在 try 块内"""
    import inspect
    from backend.v1.app.generate.controller.generation import regenerate_frame_video

    source = inspect.getsource(regenerate_frame_video)

    try_pos = source.index("try:")
    get_project_pos = source.index("ProjectService.get_project")

    assert get_project_pos > try_pos, \
        "ProjectService.get_project 应该在 try 块内"


def test_controller_retry_frame_auth_inside_try_block():
    """验证 retry 端点的鉴权代码在 try 块内"""
    import inspect
    from backend.v1.app.generate.controller.generation import retry_frame

    source = inspect.getsource(retry_frame)

    try_pos = source.index("try:")
    get_project_pos = source.index("ProjectService.get_project")

    assert get_project_pos > try_pos, \
        "ProjectService.get_project 应该在 try 块内"


def test_controller_regenerate_frame_has_catch_all_exception():
    """验证 regenerate 端点有 except Exception 兜底"""
    import inspect
    from backend.v1.app.generate.controller.generation import regenerate_frame

    source = inspect.getsource(regenerate_frame)

    assert "except Exception" in source, "应有 except Exception 兜底，避免未处理异常返回系统内部错误"
    assert "except BusinessException" in source, "应有 except BusinessException 避免被兜底吞掉"


# ── 5. 任务失败重试 → retry_count 正确持久化 ──────────────────────────────────

def test_task_reference_has_retry_count_field():
    """TaskReference 应有 retry_count 字段"""
    from backend.v1.app.generate.service.generateUtils.task_service import TaskReference

    ref = TaskReference(
        id="gen_test123",
        project_id=1,
        task_type="frame_image",
        status="queued",
        retry_count=2,
    )
    assert ref.retry_count == 2


def test_task_reference_retry_count_defaults_to_zero():
    """retry_count 默认值为 0"""
    from backend.v1.app.generate.service.generateUtils.task_service import TaskReference

    ref = TaskReference(
        id="gen_test123",
        project_id=1,
        task_type="frame_image",
        status="queued",
    )
    assert ref.retry_count == 0


def test_update_task_sync_accepts_retry_count():
    """update_task_sync 应接受 retry_count 参数"""
    import inspect
    from backend.v1.app.generate.service.generateUtils.task_service import GenerationTaskService

    sig = inspect.signature(GenerationTaskService.update_task_sync)
    assert "retry_count" in sig.parameters, "update_task_sync 应有 retry_count 参数"


def test_update_task_failure_state_passes_retry_count():
    """_update_task_failure_state 应将 retry_count 传递给 update_task_sync"""
    import inspect
    from backend.v1.app.generate.tasks.video_tasks import _update_task_failure_state

    source = inspect.getsource(_update_task_failure_state)

    # 不应该直接设置 task.retry_count（会导致 AttributeError）
    assert "task.retry_count = " not in source, \
        "不应直接修改 task.retry_count，TaskReference 是 dataclass 应通过 update_task_sync 传递"

    # 应该通过 update_task_sync 传递 retry_count
    assert "retry_count=" in source, "应通过 update_task_sync(retry_count=...) 持久化"


# ── 6. 视频任务成功路径有最终 commit ──────────────────────────────────────────

def test_frame_video_task_commits_after_state_update():
    """generate_frame_video_task 成功后应在状态更新后 commit"""
    import inspect
    from backend.v1.app.generate.tasks.video_tasks import generate_frame_video_task

    source = inspect.getsource(generate_frame_video_task)

    # 找到 update_task_sync(... status="succeeded" ...) 之后是否有 db.commit()
    succeeded_pos = source.index('status="succeeded"')
    after_succeeded = source[succeeded_pos:]

    assert "db.commit()" in after_succeeded, \
        "generate_frame_video_task 应在 update_task_sync 之后 db.commit()，否则任务成功状态不会持久化"


# ── 7. 数据库迁移文件存在 ────────────────────────────────────────────────────

def test_workflow_columns_migration_exists():
    """应有迁移文件为 projects 表添加 workflow 相关列"""
    from pathlib import Path

    migration_dir = Path(__file__).resolve().parents[3] / "resources" / "migrations"
    migration_files = list(migration_dir.glob("*workflow*"))

    assert len(migration_files) > 0, \
        f"缺少 workflow 相关列的迁移文件，请检查 {migration_dir}"

    content = migration_files[0].read_text(encoding="utf-8")
    for col in ["dirty_stage", "script_confirmed_at", "images_confirmed_at", "video_confirmed_at",
                 "workflow_stage", "stage_status", "last_task_id"]:
        assert col in content, f"迁移文件缺少 {col} 列"
