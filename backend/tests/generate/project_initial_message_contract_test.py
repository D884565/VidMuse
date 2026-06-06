from backend.v1.app.generate.service.chat.initial_message import ProjectInitialMessageBuilder
from backend.v1.app.generate.service.chat.project_title import build_video_project_title


def test_initial_user_message_does_not_append_default_duration_or_voice():
    builder = ProjectInitialMessageBuilder()

    message = builder.build(
        title="你好",
        user_prompt="你好",
        style=None,
        target_audience=None,
        key_points=[],
        avoid=[],
        target_duration=15,
        voice_type="zh_female_cancan_mars_bigtts",
        product_url=None,
        reference_images=[],
        product_info=None,
    )

    assert message["content"] == "你好"
    assert "时长" not in message["content"]
    assert "音色" not in message["content"]


def test_video_project_title_uses_product_not_full_user_prompt():
    title = build_video_project_title("生成一个电竞耳机带货视频")

    assert title == "电竞耳机带货视频"


def test_video_project_title_falls_back_when_product_is_missing():
    title = build_video_project_title("")

    assert title == "未命名视频项目"
