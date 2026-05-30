from pathlib import Path


ROOT = Path("backend/v1/app/generate")


def test_chat_service_executes_every_agent_action():
    source = (ROOT / "service/chat_service.py").read_text(encoding="utf-8")

    for action in (
        "GENERATE_SCRIPT",
        "CONFIRM_SCRIPT_AND_GENERATE_IMAGES",
        "REGENERATE_FRAME_IMAGE",
        "CONFIRM_IMAGES_AND_GENERATE_VIDEO",
        "CONFIRM_VIDEO",
        "UPDATE_SCRIPT_TEXT",
        "ASK_CLARIFYING_QUESTION",
    ):
        assert f'plan["action"] == "{action}"' in source


def test_workflow_advance_submits_image_task_without_inline_generation():
    source = (ROOT / "controller/generation.py").read_text(encoding="utf-8")

    assert "submit_image_task" in source
    assert "await image_workflow_service.generate_images(db, project_id)" not in source


def test_failed_frame_image_is_not_saved_as_real_image_url():
    source = (ROOT / "service/image_generation_service.py").read_text(encoding="utf-8")

    assert "frame.image_url = placeholder_url" not in source
    assert "frame.image_url = None" in source
    assert "frame.status == 2 and frame.image_url" in source


def test_video_task_aborts_when_images_or_videos_fail():
    source = (ROOT / "temp/video_tasks.py").read_text(encoding="utf-8")

    assert "IMAGE_GENERATION_FAILED" in source
    assert "VIDEO_SEGMENT_GENERATION_FAILED" in source
    assert "raise RuntimeError" in source


def test_video_composer_refuses_failed_or_missing_image_frames():
    source = (ROOT / "service/video_composer.py").read_text(encoding="utf-8")

    assert "validate_frames_for_video" in source
    assert "status == 3" in source
    assert "missing image_url" in source


def test_project_detail_does_not_query_all_user_assets():
    source = (ROOT / "service/video_generation.py").read_text(encoding="utf-8")

    assert "Asset.user_id == project.user_id" not in source
    assert "projects/{project_id}/" in source
