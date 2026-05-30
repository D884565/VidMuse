from pathlib import Path


def test_frontend_has_storyboard_timeline_component():
    source = Path("frontend/src/components/Workflow/StoryboardTimeline.jsx").read_text(encoding="utf-8")

    assert "dirty" in source
    assert "duration" in source
    assert "status" in source


def test_frontend_project_service_has_export_and_asset_methods():
    source = Path("frontend/src/services/project.js").read_text(encoding="utf-8")

    assert "exportProjectVideo" in source
    assert "bindProjectAsset" in source


def test_project_polling_does_not_treat_script_ready_as_terminal():
    source = Path("frontend/src/hooks/useProjectPolling.js").read_text(encoding="utf-8")

    terminal_line = next(line for line in source.splitlines() if "TERMINAL_STATUSES" in line)
    assert "script_ready" not in terminal_line
    assert "stage_status === 'running'" in source


def test_frame_grid_uses_workflow_status_for_busy_and_render_controls():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "project?.stage_status === 'running'" in source
    assert "project?.workflow_stage === 'video'" in source


def test_chat_container_uses_same_project_detail_hook_as_frame_grid():
    source = Path("frontend/src/components/Chat/ChatContainer.jsx").read_text(encoding="utf-8")

    assert "useProjectPolling" in source
    assert "useWorkflowProject" not in source


def test_chat_input_does_not_offer_fake_file_send_path():
    use_chat_source = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")
    input_source = Path("frontend/src/components/Input/SmartInput.jsx").read_text(encoding="utf-8")

    assert "files = []" not in use_chat_source
    assert "onSend(value, files)" not in input_source
