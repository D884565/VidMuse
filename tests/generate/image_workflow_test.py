from backend.v1.app.generate.service.image_workflow import build_image_stage_message


class Frame:
    id = 1
    sequence = 1
    image_url = "https://cdn.test/1.png"
    status = 2
    error_message = None
    description = "商品在桌面上"


def test_build_image_stage_message_contains_image_grid_and_actions():
    message = build_image_stage_message([Frame()], task_id=9)
    block_types = [block["type"] for block in message["blocks"]]

    assert "image_grid" in block_types
    assert "action_bar" in block_types
    assert message["task_id"] == 9
