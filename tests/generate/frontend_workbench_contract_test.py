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
