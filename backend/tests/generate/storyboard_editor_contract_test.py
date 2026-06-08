from pathlib import Path


def test_storyboard_service_supports_sequence_and_dirty_stage():
    source = Path("backend/v1/app/generate/service/generateUtils/storyboard.py").read_text(encoding="utf-8")

    assert '"sequence"' in source
    assert "invalidate_from" in source
    assert "validate_total_frame_duration" in source


def test_storyboard_service_uses_granular_invalidation_and_script_sync():
    source = Path("backend/v1/app/generate/service/generateUtils/storyboard.py").read_text(encoding="utf-8")

    assert "_infer_dirty_stage" in source
    assert '"narration"' in source
    assert '"image_prompt"' in source
    assert '"video_prompt"' in source
    assert "_sync_project_script_snapshot" in source


def test_storyboard_warning_paths_mark_dirty_before_returning():
    source = Path("backend/v1/app/generate/service/generateUtils/storyboard.py").read_text(encoding="utf-8")
    changed_section = source[source.index("if changed:"):source.index("return self._frame_to_dict(frame)")]

    for warning in ('"warning": "total_duration_overflow"', '"warning": "narration_overflow"'):
        warning_index = changed_section.index(warning)
        before_warning = changed_section[:warning_index]
        assert "frame.dirty = 1" in before_warning
        assert "generation_workflow_service.invalidate_from(project, dirty_stage)" in before_warning
        assert "await self._sync_project_script_snapshot(db, project, frames)" in before_warning


def test_storyboard_sync_clears_legacy_description_for_empty_image_prompt_and_validates_sequence():
    source = Path("backend/v1/app/generate/service/generateUtils/storyboard.py").read_text(encoding="utf-8")

    assert "value = max(1, int(value))" in source
    assert "frame.description = frame.image_prompt" in source


def test_controller_exposes_frame_local_generation_routes():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "/frames/{frame_id}/regenerate-image" in source
    assert "/frames/{frame_id}/regenerate-video" in source
    assert '"frame_video"' in source


def test_frame_image_regenerate_route_dispatches_task_and_preserves_instruction():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    route = source[source.index("async def regenerate_frame_image("):source.index("@router.post", source.index("async def regenerate_frame_image(") + 1)]

    assert 'generation_task_service.create_task(db, project_id, "frame_image", status="queued")' in route
    assert 'celery_app.send_task("generate_frame_image_task", args=[project_id, frame_id, task.id])' in route
    assert 'instruction = (req or {}).get("instruction")' in route
    assert 'task_id": task.id' in route


def test_frame_video_route_persists_instruction_for_worker_prompt():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    route = source[source.index("async def regenerate_frame_video("):source.index("@router.post", source.index("async def regenerate_frame_video(") + 1)]

    assert 'instruction = (req or {}).get("instruction")' in route
    assert 'video_revision_instruction' in route


def test_storyboard_detail_actions_write_conversation_audit_messages():
    generation_source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    storyboard_source = Path("backend/v1/app/generate/service/generateUtils/storyboard.py").read_text(encoding="utf-8")

    assert "Conversation(" in generation_source or "Conversation(" in storyboard_source
    assert "storyboard_edit" in generation_source or "storyboard_edit" in storyboard_source
    assert "frame_id" in generation_source


def test_storyboard_detail_save_message_does_not_fall_back_to_internal_frame_id():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    route = source[source.index("async def update_project_frame("):source.index("@router.post", source.index("async def update_project_frame("))]

    assert "frame.get('sequence') or frame_id" not in route
    assert "已保存分镜修改" in route


def test_frame_video_route_requires_current_image_before_dispatch():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    route = source[source.index("async def regenerate_frame_video("):source.index("@router.post", source.index("async def regenerate_frame_video(") + 1)]

    assert "if not frame.image_url or frame.status != 2 or frame.dirty" in route
    assert "请先重新生成图片" in route
    assert "Conversation(" in route


def test_frame_image_task_clears_dirty_after_success_so_video_can_follow():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")
    task = source[source.index("def generate_frame_image_task("):source.index("except SoftTimeLimitExceeded", source.index("def generate_frame_image_task("))]

    assert "frame.dirty = 0" in task


def test_retry_endpoint_does_not_submit_full_project_render_anymore():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    retry_start = source.index('async def retry_frame(')
    retry_end = source.find('@router', retry_start + 1)
    body = source[retry_start: retry_end if retry_end != -1 else len(source)]

    assert "submit_generation_task" not in body
    assert '"frame_video"' in body or '"frame_image"' in body
