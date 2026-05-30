from backend.v1.app.generate.service.workflow_blocks import build_script_stage_blocks


class Frame:
    id = 1
    sequence = 1
    duration = 3
    description = "镜头画面"
    narration = "旁白"
    image_prompt = "图片提示"
    video_prompt = "视频提示"
    prompt = "视频提示"


def test_script_stage_blocks_include_summary_table_and_actions():
    blocks = build_script_stage_blocks([Frame()])

    assert [block["type"] for block in blocks] == ["script_summary", "storyboard_table", "action_bar"]
