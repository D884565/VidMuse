from backend.v1.app.generate.service.project_initial_message import (
    ProjectInitialMessageBuilder,
)


def test_builds_initial_message_from_project_fields():
    message = ProjectInitialMessageBuilder().build(
        title="耳机带货视频创作",
        user_prompt="生成一个耳机带货视频",
        style="真实写实",
        target_audience="年轻通勤人群",
        key_points=["佩戴舒适", "续航强"],
        avoid=["夸张科幻"],
        target_duration=15,
        voice_type="zh_female_cancan_mars_bigtts",
        product_url="https://example.com/product",
        reference_images=[],
        product_info=None,
    )

    assert message["role"] == "user"
    assert "生成一个耳机带货视频" in message["content"]
    assert "真实写实" in message["content"]
    assert "年轻通勤人群" in message["content"]
    assert "佩戴舒适、续航强" in message["content"]
    assert "约 15 秒" in message["content"]
    assert message["stage"] == "project_start"
    assert message["message_type"] == "asset"


def test_builds_asset_blocks_from_reference_and_product_images():
    message = ProjectInitialMessageBuilder().build(
        title="耳机带货视频创作",
        user_prompt="",
        style=None,
        target_audience=None,
        key_points=[],
        avoid=[],
        target_duration=15,
        voice_type="voice",
        product_url="https://example.com/product",
        reference_images=["https://cdn.example.com/ref.png"],
        product_info={
            "title": "Redmi 耳机",
            "main_images": ["https://cdn.example.com/main.png"],
            "description": "无线耳机",
        },
    )

    block_types = [block["type"] for block in message["blocks"]]
    assert "product_card" in block_types
    assert "asset_grid" in block_types

    product_block = next(block for block in message["blocks"] if block["type"] == "product_card")
    assert product_block["title"] == "Redmi 耳机"
    assert product_block["url"] == "https://example.com/product"

    asset_block = next(block for block in message["blocks"] if block["type"] == "asset_grid")
    urls = [item["url"] for item in asset_block["items"]]
    assert "https://cdn.example.com/ref.png" in urls
    assert "https://cdn.example.com/main.png" in urls
