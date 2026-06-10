from types import SimpleNamespace

from backend.v1.app.generate.service.generateUtils.project import (
    _is_noise_created_project,
    _project_to_dict,
)


def make_project(workflow_stage, stage_status):
    return SimpleNamespace(
        id=1,
        title="test",
        description=None,
        summary=None,
        product_url=None,
        video_output_url=None,
        audio_url=None,
        user_id=1,
        status="review_required",
        workflow_stage=workflow_stage,
        stage_status=stage_status,
        created_at=None,
        updated_at=None,
    )


def test_project_list_status_name_distinguishes_video_review_from_script_ready():
    project = make_project("video", "awaiting_review")

    data = _project_to_dict(project)

    assert data["workflow_stage"] == "video"
    assert data["stage_status"] == "awaiting_review"
    assert data["status_name"] == "视频待确认"


def test_project_list_status_name_distinguishes_image_review_from_script_ready():
    project = make_project("image", "awaiting_review")

    data = _project_to_dict(project)

    assert data["status_name"] == "图片待确认"


def test_project_list_filters_created_idle_greeting_noise_project():
    project = make_project("created", "idle")
    project.title = "你好"
    project.summary = "你好"
    project.user_prompt = "你好"
    project.product_url = None
    project.video_output_url = None

    assert _is_noise_created_project(project, frame_count=0) is True


def test_project_list_keeps_created_idle_video_request_project():
    project = make_project("created", "idle")
    project.title = "生成一个电竞耳机带货视频"
    project.summary = "生成一个电竞耳机带货视频"
    project.user_prompt = "生成一个电竞耳机带货视频"
    project.product_url = None
    project.video_output_url = None

    assert _is_noise_created_project(project, frame_count=0) is False


def test_project_list_keeps_created_idle_request_without_explicit_generate_word():
    project = make_project("created", "idle")
    project.title = "吉他带货视频"
    project.summary = "创建一个吉他带货视频"
    project.user_prompt = "创建一个吉他带货视频"
    project.product_url = None
    project.video_output_url = None

    assert _is_noise_created_project(project, frame_count=0) is False
