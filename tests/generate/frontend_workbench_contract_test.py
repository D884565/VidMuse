from pathlib import Path


def test_frontend_has_storyboard_timeline_component():
    source = Path("frontend/src/components/Workflow/StoryboardTimeline.jsx").read_text(encoding="utf-8")

    assert "dirty" in source
    assert "duration" in source
    assert "status" in source


def test_frontend_project_service_has_export_and_asset_methods():
    source = Path("frontend/src/services/project.js").read_text(encoding="utf-8")

    assert "downloadProjectVideo" in source
    assert "responseType: 'blob'" in source or 'responseType: "blob"' in source
    assert "bindProjectAsset" in source


def test_project_polling_does_not_treat_script_ready_as_terminal():
    source = Path("frontend/src/hooks/useProjectPolling.js").read_text(encoding="utf-8")

    # 终态判断应基于 workflow 字段，不依赖旧 status 字符串
    assert "TERMINAL_STATUSES" not in source  # 已移除旧常量
    assert "isProjectTerminal" in source  # 使用 workflow 字段推导终态
    assert "stage_status === 'running'" in source
    assert "script_ready" not in source  # 不应硬编码旧 status 值


def test_frame_grid_uses_workflow_status_for_busy_and_render_controls():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "project?.stage_status === 'running'" in source
    assert "project?.workflow_stage === 'video'" in source


def test_frame_grid_has_single_frame_video_regenerate_and_edit_entrypoints():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "regenerateFrameVideo" in source
    assert "updateFrame" in source
    assert "handleRegenerateVideo" in source
    assert "handleSaveFrameEdit" in source


def test_frame_grid_polls_active_task_and_surfaces_retry_and_action_guidance():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "setInterval" in source
    assert "RETRYING" in source
    assert "actionMessage" in source


def test_frame_grid_uses_direct_download_export_flow():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "downloadProjectVideo" in source
    assert "exportProjectVideo" not in source
    assert "Download started" in source or "download has started" in source.lower()


def test_chat_container_uses_same_project_detail_hook_as_frame_grid():
    source = Path("frontend/src/components/Chat/ChatContainer.jsx").read_text(encoding="utf-8")

    assert "useProjectPolling" in source
    assert "useWorkflowProject" not in source


def test_active_frontend_paths_do_not_import_removed_legacy_modules():
    for path in (
        "frontend/src/components/Layout/MainLayout.jsx",
        "frontend/src/components/Layout/Sidebar.jsx",
        "frontend/src/components/Chat/ChatContainer.jsx",
        "frontend/src/components/Keyframes/FrameGrid.jsx",
        "frontend/src/hooks/useChat.js",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "useWorkflowProject" not in source
        assert "KeyframeStudio" not in source
        assert "MergePanel" not in source
        assert "useFileUpload" not in source
        assert "FilePreview" not in source


def test_chat_input_does_not_offer_fake_file_send_path():
    use_chat_source = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")
    input_source = Path("frontend/src/components/Input/SmartInput.jsx").read_text(encoding="utf-8")

    assert "files = []" not in use_chat_source
    assert "onSend(value, files)" not in input_source
