from pathlib import Path

from backend.v1.app.generate.service.stages.image_service import ImageGenerationService


ROOT = Path("backend/v1/app/generate")


def test_chat_service_executes_every_agent_action():
    source = (ROOT / "service/chat/chat_service.py").read_text(encoding="utf-8")

    for action in (
        "GENERATE_SCRIPT",
        "CONFIRM_AND_ADVANCE",
        "REGENERATE_FRAME_IMAGE",
        "REGENERATE_FRAME_VIDEO",
        "REGENERATE_TTS",
        "CHANGE_BGM",
        "CONVERSE",
        "ASK_CLARIFYING",
    ):
        assert f'action == "{action}"' in source or f'plan["action"] == "{action}"' in source


def test_workflow_advance_submits_image_task_without_inline_generation():
    source = (ROOT / "controller/generation.py").read_text(encoding="utf-8")

    assert "submit_image_task" in source
    assert "await image_workflow_service.generate_images(db, project_id)" not in source


def test_failed_frame_image_is_not_saved_as_real_image_url():
    class Frame:
        id = 1
        sequence = 1
        status = 0
        image_url = "https://cdn.test/old.png"
        description = "商品在桌面上"

    service = ImageGenerationService()

    def fail_generation(*args, **kwargs):
        raise RuntimeError("boom")

    service._call_text_to_image = fail_generation
    frame = Frame()

    service.generate_frame_images([frame], project_id=1)

    assert frame.image_url is None
    assert frame.status == 3
    assert "boom" in frame.error_message


def test_video_task_aborts_when_images_or_videos_fail():
    source = (ROOT / "tasks/video_tasks.py").read_text(encoding="utf-8")

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
    assert "ProjectAsset" in source
    assert "Asset.url.contains" not in source


def test_frame_and_script_models_declare_uniqueness_constraints():
    frame_source = Path("backend/v1/app/models/frame.py").read_text(encoding="utf-8")
    script_source = Path("backend/v1/app/models/script.py").read_text(encoding="utf-8")

    assert "uq_frames_project_sequence" in frame_source
    assert "UniqueConstraint" in frame_source
    assert "uq_scripts_project_version" in script_source
