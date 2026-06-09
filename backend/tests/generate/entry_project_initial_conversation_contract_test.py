from pathlib import Path

from backend.v1.app.generate.service.chat.initial_message import ProjectInitialMessageBuilder


def test_initial_user_message_uses_entry_display_prompt_for_chat_history():
    builder = ProjectInitialMessageBuilder()

    message = builder.build(
        title="防晒喷雾带货视频",
        user_prompt="做一条防晒喷雾带货视频\n\n参考素材：\n1. [图片] 防晒喷雾主图（asset_id: 101）",
        display_user_prompt="做一条防晒喷雾带货视频",
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

    assert message["role"] == "user"
    assert message["content"] == "做一条防晒喷雾带货视频"
    assert message["metadata"]["source"] == "project_create"
    assert message["metadata"]["original_user_prompt"].startswith("做一条防晒喷雾带货视频\n\n参考素材")
    assert message["metadata"]["display_content"] == "做一条防晒喷雾带货视频"


def test_create_project_initializes_optional_product_before_title_generation():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    create_section = source[source.index("async def create_project"):source.index("async def get_project")]

    assert "product_obj = None" in create_section
    assert create_section.index("product_obj = None") < create_section.index("if project.product_id:")
    assert "display_user_prompt=project.display_user_prompt" in create_section
