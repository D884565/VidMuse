from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_chat_script_generation_binds_selected_assets_and_forces_regeneration():
    source = read("backend/v1/app/generate/service/chat/chat_service.py")

    assert "def _bind_selected_assets_to_project" in source
    assert "metadata or {}" in source
    assert '"selected_assets"' in source
    assert "force=True" in source
    assert "ProjectAsset(" in source


def test_chat_action_execution_is_shared_by_streaming_and_non_streaming_paths():
    source = read("backend/v1/app/generate/service/chat/chat_service.py")

    assert "async def _execute_action(" in source
    assert source.count("await self._execute_action(") >= 2


def test_bgm_selection_is_persisted_and_excludes_current_bgm():
    chat_source = read("backend/v1/app/generate/service/chat/chat_service.py")
    task_source = read("backend/v1/app/generate/tasks/video_tasks.py")
    project_source = read("backend/v1/app/models/project.py")
    bgm_selector_source = read("backend/v1/app/generate/service/stages/bgm_selector.py")

    assert "music_config" in project_source
    assert "current_bgm_id" in chat_source
    assert "exclude_ids" in chat_source
    assert "await bgm_selector_service.select_bgm_async(" in chat_source
    assert "async def select_bgm_async(" in bgm_selector_source
    assert "async def _get_candidates_async(" in bgm_selector_source
    assert "current_bgm_id" in task_source


def test_frame_image_task_writes_conversation_message_after_success():
    task_source = read("backend/v1/app/generate/tasks/video_tasks.py")

    assert "def _write_frame_image_regeneration_conversation" in task_source
    assert "REGENERATE_FRAME_IMAGE" in task_source
    assert '"image_grid"' in task_source
    assert "Conversation(" in task_source


def test_frame_video_task_writes_conversation_message_after_success():
    task_source = read("backend/v1/app/generate/tasks/video_tasks.py")

    assert "def _write_frame_video_regeneration_conversation" in task_source
    assert "REGENERATE_FRAME_VIDEO" in task_source
    assert '"video_card"' not in task_source[task_source.index("def _write_frame_video_regeneration_conversation"):task_source.index("def _generate_single_frame_video")]
    assert '"follow_up"' in task_source
    assert "_write_frame_video_regeneration_conversation(db, project, frame, task_id)" in task_source


def test_image_workflow_imports_json_and_conversation():
    source = read("backend/v1/app/generate/service/stages/image_workflow.py")

    assert "import json" in source
    assert "from backend.v1.app.models.conversation import Conversation" in source


def test_parallel_video_generation_does_not_mutate_orm_in_worker_threads():
    source = read("backend/v1/app/generate/tasks/video_tasks.py")
    worker_section = source[
        source.index("def _generate_single_frame_video"):
        source.index("def _generate_frame_videos_parallel")
    ]

    assert "frame.dirty =" not in worker_section
    assert "return {" in worker_section
    assert "video_url" in worker_section


def test_frontend_project_editor_refreshes_conversations_and_applies_updated_frames():
    source = read("frontend/src/hooks/useProjectEditor.js")

    assert "bumpConversationVersion" in source
    assert "applyFrameUpdates" in source
    assert "applyProjectSnapshot" in source
    assert "result?.updated_frames" in source
    assert "result?.workflow_stage" in source


def test_frontend_polling_stops_for_stable_review_state():
    source = read("frontend/src/hooks/useProjectPolling.js")

    assert "stableReview" in source
    assert "clearInterval(intervalRef.current)" in source
    assert "applyFrameUpdates" in source


def test_frontend_polling_can_merge_workflow_state_from_chat_done_event():
    source = read("frontend/src/hooks/useProjectPolling.js")

    assert "applyProjectSnapshot" in source
    assert "workflow_stage: snapshot.workflow_stage" in source
    assert "stage_status: snapshot.stage_status" in source


def test_frontend_polling_refetch_restarts_interval_and_task_completion_refreshes_frames():
    polling_source = read("frontend/src/hooks/useProjectPolling.js")
    frame_source = read("frontend/src/components/Keyframes/FrameGrid.jsx")

    assert "startPolling" in polling_source
    assert "stopPolling()" in polling_source
    assert "startPolling()" in polling_source
    assert "lastTerminalTaskIdRef" in frame_source
    assert "TERMINAL_TASK_STATUSES.includes(task.status)" in frame_source
    assert "refetch()" in frame_source


def test_frame_grid_sends_changed_fields_only_and_handles_edit_warnings():
    source = read("frontend/src/components/Keyframes/FrameGrid.jsx")

    assert "buildFramePatch(editingFrame, editForm)" in source
    assert "Object.keys(patch).length" in source
    assert "requires_confirmation" in source
    assert "pendingEditWarning" in source


def test_streaming_workflow_actions_execute_and_persist_before_success_events():
    source = read("backend/v1/app/generate/service/chat/chat_service.py")
    stream_section = source[
        source.index("async def handle_message_stream("):
        source.index("async def _handle_confirm_and_advance(")
    ]

    non_converse_branch = stream_section[
        stream_section.index('if action not in ("CONVERSE", "ASK_CLARIFYING"):'):
        stream_section.index('else:', stream_section.index('if action not in ("CONVERSE", "ASK_CLARIFYING"):'))
    ]

    assert "await self._execute_action(" in non_converse_branch
    assert "db.add(assistant_message)" in non_converse_branch
    assert non_converse_branch.index("await self._execute_action(") < non_converse_branch.index("db.add(assistant_message)")
    assert non_converse_branch.index("await db.commit()") < non_converse_branch.index('yield sse("token"')
    assert stream_section.index("await db.commit()", stream_section.index('if action not in ("CONVERSE", "ASK_CLARIFYING"):')) < stream_section.index('yield sse("blocks"')


def test_main_layout_conditionally_renders_active_view_only():
    source = read("frontend/src/components/Layout/MainLayout.jsx")

    assert "activeView === 'keyframes' && <FrameGrid" in source
    assert "display: activeView" not in source


def test_creation_mode_lives_in_app_store():
    store_source = read("frontend/src/store/appStore.js")
    frame_source = read("frontend/src/components/Keyframes/FrameGrid.jsx")
    workbench_source = read("frontend/src/components/Workbench/WorkbenchView.jsx")

    assert "creationMode:" in store_source
    assert "setCreationMode:" in store_source
    assert "useState('independent')" not in frame_source
    assert "useState('independent')" not in workbench_source
