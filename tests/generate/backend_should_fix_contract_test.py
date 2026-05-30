from pathlib import Path
from types import SimpleNamespace

from backend.v1.app.generate.service.reference_image_utils import (
    extract_reference_images,
    select_reference_images,
)


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_reference_image_extraction_is_user_first_deduped_and_limited():
    project = SimpleNamespace(
        reference_images=["https://cdn.test/user-1.png", "", "https://cdn.test/shared.png"],
        product_info='{"main_images": ["https://cdn.test/shared.png", "https://cdn.test/product-1.png"]}',
    )

    assert extract_reference_images(project) == [
        "https://cdn.test/user-1.png",
        "https://cdn.test/shared.png",
        "https://cdn.test/product-1.png",
    ]

    many = [f"https://cdn.test/{i}.png" for i in range(20)]
    assert select_reference_images(reference_images=many) == many[:14]


def test_video_tasks_use_shared_sync_session_and_failure_helper():
    source = read("backend/v1/app/generate/temp/video_tasks.py")

    assert "from backend.store.database.sync_database import SessionLocal" in source
    assert "create_engine(" not in source
    assert "def _update_task_failure_state(" in source
    assert source.count("_update_task_failure_state(") >= 5


def test_video_task_try_blocks_do_not_commit_project_failed_before_retry_handler():
    source = read("backend/v1/app/generate/temp/video_tasks.py")

    assert "def _mark_project_failed" in source
    assert "db.commit()\n\n\ndef _update_task_failure_state" not in source
    for marker in ('_mark_project_failed(db, project_id, "image")', '_mark_project_failed(db, project_id, "video")'):
        assert marker not in source


def test_failure_state_updates_retry_count_when_retrying():
    source = read("backend/v1/app/generate/temp/video_tasks.py")

    assert "retry_count" in source
    assert "will_retry" in source


def test_video_task_raises_stage_specific_errors_for_image_and_video_failures():
    source = read("backend/v1/app/generate/temp/video_tasks.py")

    assert "class GenerationStageError" in source
    assert 'stage="image"' in source
    assert 'current_step="IMAGE_GENERATION_FAILED"' in source
    assert 'stage="video"' in source
    assert 'current_step="VIDEO_SEGMENT_GENERATION_FAILED"' in source


def test_video_task_failure_handler_uses_error_stage_metadata():
    source = read("backend/v1/app/generate/temp/video_tasks.py")

    assert 'stage=getattr(exc, "stage", "video")' in source
    assert 'current_step=getattr(exc, "current_step", "FAILED")' in source
    assert 'error_code=getattr(exc, "error_code", "VIDEO_GENERATION_FAILED")' in source


def test_frame_and_export_tasks_retry_before_final_failure():
    source = read("backend/v1/app/generate/temp/video_tasks.py")

    for task_name in ("generate_frame_image_task", "generate_frame_video_task", "export_video_task"):
        start = source.index(f"def {task_name}")
        next_task = source.find("@celery_app.task", start + 1)
        body = source[start: next_task if next_task != -1 else len(source)]
        assert "will_retry = self.request.retries < self.max_retries" in body
        assert "raise self.retry(exc=exc)" in body


def test_project_detail_uses_project_asset_join_not_url_contains():
    source = read("backend/v1/app/generate/service/video_generation.py")

    assert "ProjectAsset" in source
    assert ".join(ProjectAsset" in source or "join(ProjectAsset" in source
    assert "Asset.url.contains" not in source
    assert '"role":' in source


def test_workflow_mutations_lock_project_row():
    source = read("backend/v1/app/generate/controller/generation.py")

    assert "def _load_project_for_workflow_update" in source
    assert ".with_for_update()" in source
    assert source.count("_load_project_for_workflow_update(db, project_id)") >= 2
