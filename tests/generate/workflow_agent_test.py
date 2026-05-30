from backend.v1.app.generate.service.workflow_agent import WorkflowAgentService


class Project:
    workflow_stage = "image"
    stage_status = "awaiting_review"


class Frame:
    id = 33
    sequence = 3


def test_agent_maps_confirm_images_to_generate_video():
    plan = WorkflowAgentService().plan(Project(), [], "确认图片，生成视频")

    assert plan["action"] == "CONFIRM_IMAGES_AND_GENERATE_VIDEO"
    assert plan["affected_stage"] == "image"
    assert plan["next_stage"] == "video"


def test_agent_extracts_frame_sequence_for_image_regeneration():
    plan = WorkflowAgentService().plan(Project(), [Frame()], "第3张图换成咖啡馆窗边")

    assert plan["action"] == "REGENERATE_FRAME_IMAGE"
    assert plan["affected_frame_ids"] == [33]
    assert plan["requires_confirmation"] is False
