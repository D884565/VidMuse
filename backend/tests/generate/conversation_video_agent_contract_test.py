from types import SimpleNamespace
from pathlib import Path

from backend.v1.app.generate.service.workflow.agent import workflow_agent_service
from backend.v1.app.generate.service.chat.chat_service import ChatService
from backend.v1.app.generate.service.chat.chat_service import apply_frame_modifications
from backend.v1.app.generate.service.workflow.media_resolvers import (
    resolve_image_generation_prompt,
    resolve_tts_text,
    resolve_video_generation_prompt,
)
from backend.v1.app.generate.service.workflow.llm_agent import LLMAgentService, VALID_ACTIONS


def test_image_generation_prompt_uses_image_prompt_and_revision_instruction():
    frame = SimpleNamespace(
        description="old description",
        image_prompt="bright kitchen product shot",
        ai_params={"image_revision_instruction": "make the product closer"},
    )

    prompt = resolve_image_generation_prompt(frame)

    assert "bright kitchen product shot" in prompt
    assert "make the product closer" in prompt
    assert "old description" not in prompt


def test_video_generation_prompt_prefers_video_prompt():
    frame = SimpleNamespace(
        prompt="legacy prompt",
        description="description",
        video_prompt="slow push-in with steam rising",
        ai_params={},
    )

    assert resolve_video_generation_prompt(frame) == "slow push-in with steam rising"


def test_chat_frame_description_edit_keeps_image_prompt_in_sync():
    frame = SimpleNamespace(
        description="主体是女生拿着保温杯",
        image_prompt="女生拿着保温杯站在画面中心",
        video_prompt="镜头推进",
        narration="冬天喝热水",
        duration=4,
    )

    apply_frame_modifications(frame, {"description": "主体是年纪男生拿着冒热气的保温杯"})

    assert frame.description == "主体是年纪男生拿着冒热气的保温杯"
    assert frame.image_prompt == "主体是年纪男生拿着冒热气的保温杯"


def test_tts_text_prefers_narration():
    frame = SimpleNamespace(
        narration="new concise narration",
        description="description fallback",
        ai_params={"text": "legacy text"},
    )

    assert resolve_tts_text(frame) == "new concise narration"


def test_llm_agent_supports_stage_and_tts_actions():
    assert "GENERATE_IMAGES" in VALID_ACTIONS
    assert "GENERATE_VIDEO" in VALID_ACTIONS
    assert "REGENERATE_TTS" in VALID_ACTIONS
    assert "REGENERATE_PROJECT_ALL" in VALID_ACTIONS
    assert "REGENERATE_IMAGES_AND_VIDEO" in VALID_ACTIONS
    assert "REGENERATE_VIDEO_ONLY" in VALID_ACTIONS

    service = LLMAgentService()

    assert service._infer_affected_stage("GENERATE_IMAGES") == "image"
    assert service._infer_affected_stage("GENERATE_VIDEO") == "video"
    assert service._infer_affected_stage("REGENERATE_TTS") == "video"
    assert service._infer_affected_stage("REGENERATE_PROJECT_ALL") == "script"
    assert service._infer_affected_stage("REGENERATE_IMAGES_AND_VIDEO") == "image"
    assert service._infer_affected_stage("REGENERATE_VIDEO_ONLY") == "video"


def test_chat_service_has_real_generation_action_branches():
    source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")

    assert 'plan["action"] == "GENERATE_IMAGES"' in source
    assert 'plan["action"] == "GENERATE_VIDEO"' in source
    assert 'plan["action"] == "REGENERATE_TTS"' in source
    assert 'plan["action"] in PROJECT_REGENERATION_ACTIONS' in source
    assert "def _submit_project_regeneration(" in source
    assert '"generate_frame_image_task"' in source
    assert '"generate_frame_video_task"' in source


def test_tts_regeneration_has_audio_only_celery_task_and_chat_schedules_it():
    task_source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")
    chat_source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")

    assert 'name="generate_project_tts_task"' in task_source
    assert "def generate_project_tts_task" in task_source
    assert "_build_project_audio_track(project, frames)" in task_source
    assert 'audio_object = f"projects/{project_id}/audio.mp3"' in task_source
    assert "generate_project_tts_task" in chat_source


def test_pending_actions_are_persisted_and_exposed_by_controller():
    blocks_source = Path("backend/v1/app/generate/service/workflow/blocks.py").read_text(encoding="utf-8")
    chat_source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")
    controller_source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "pending_action_id" in blocks_source
    assert '"pending_action"' in chat_source
    assert 'status": "pending"' in chat_source
    assert "/pending-actions/{pending_action_id}/confirm" in controller_source
    assert "/pending-actions/{pending_action_id}/cancel" in controller_source


def test_stage_blocks_are_conversational_without_action_buttons():
    blocks_source = Path("backend/v1/app/generate/service/workflow/blocks.py").read_text(encoding="utf-8")

    for start, end in (
        ("def build_script_stage_blocks", "def build_image_stage_blocks"),
        ("def build_image_stage_blocks", "def build_video_stage_blocks"),
        ("def build_video_stage_blocks", "def build_frame_editor_block"),
    ):
        section = blocks_source[blocks_source.index(start):blocks_source.index(end)]
        assert '"type": "action_bar"' not in section
    assert "确认并生成图片" not in blocks_source
    assert "重新生成剧本" not in blocks_source
    assert "确认并生成视频" not in blocks_source
    assert "follow_up" in blocks_source


def test_rule_agent_starts_script_for_short_product_video_request_when_llm_falls_back():
    project = SimpleNamespace(workflow_stage="created", stage_status="idle")

    plan = workflow_agent_service.plan(
        project,
        [],
        "生成一个耳机带货视频；时长：约15秒；音色：zh_female_cancan_mars_bigtts",
    )

    assert plan["action"] == "GENERATE_SCRIPT"
    assert plan["affected_stage"] == "script"


def test_rule_agent_starts_script_for_plain_short_chinese_product_request():
    project = SimpleNamespace(workflow_stage="created", stage_status="idle")

    plan = workflow_agent_service.plan(
        project,
        [],
        "\u751f\u6210\u4e00\u4e2a\u8033\u673a\u5e26\u8d27\u89c6\u9891",
    )

    assert plan["action"] == "GENERATE_SCRIPT"
    assert plan["affected_stage"] == "script"


def test_rule_agent_regenerates_tts_when_voice_or_narration_changes():
    project = SimpleNamespace(workflow_stage="video", stage_status="awaiting_review")

    plan = workflow_agent_service.plan(
        project,
        [],
        "\u91cd\u65b0\u751f\u6210\u914d\u97f3\uff0c\u97f3\u8272\u6362\u6210\u5973\u58f0",
    )

    assert plan["action"] == "REGENERATE_TTS"
    assert plan["affected_stage"] == "video"


def test_rule_agent_detects_three_project_regeneration_modes():
    project = SimpleNamespace(workflow_stage="completed", stage_status="confirmed")

    all_plan = workflow_agent_service.plan(project, [], "这个项目全部重跑一遍，从剧本开始重新生成")
    image_video_plan = workflow_agent_service.plan(project, [], "剧本不变，图片和视频重新生成")
    video_only_plan = workflow_agent_service.plan(project, [], "剧本和图片都不变，只重新生成视频")

    assert all_plan["action"] == "REGENERATE_PROJECT_ALL"
    assert all_plan["requires_confirmation"] is True
    assert image_video_plan["action"] == "REGENERATE_IMAGES_AND_VIDEO"
    assert image_video_plan["requires_confirmation"] is True
    assert video_only_plan["action"] == "REGENERATE_VIDEO_ONLY"
    assert video_only_plan["requires_confirmation"] is True


def test_project_regeneration_actions_are_confirmed_pending_actions():
    chat_source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")

    assert "PROJECT_REGENERATION_ACTIONS" in chat_source
    assert "build_confirmation_preview_block(" in chat_source
    assert "_submit_project_regeneration(db, project, project_id, plan[\"action\"])" in chat_source


def test_rule_agent_regenerates_script_from_failed_script_stage():
    project = SimpleNamespace(workflow_stage="script", stage_status="failed")

    plan = workflow_agent_service.plan(
        project,
        [],
        "\u91cd\u65b0\u751f\u6210\u4e00\u4e2a\u7535\u7ade\u8033\u673a\u5e26\u8d27\u89c6\u9891",
    )

    assert plan["action"] == "GENERATE_SCRIPT"
    assert plan["affected_stage"] == "script"


def test_chat_service_prefers_rule_script_generation_over_llm_clarifying_on_created_project():
    service = ChatService()
    project = SimpleNamespace(workflow_stage="created", stage_status="idle")
    llm_plan = {"action": "ASK_CLARIFYING", "assistant_content": "need more info"}
    rule_plan = {
        "action": "GENERATE_SCRIPT",
        "affected_stage": "script",
        "affected_frame_ids": [],
        "assistant_content": "start script",
    }

    selected = service._prefer_rule_script_generation_for_created_project(project, llm_plan, rule_plan)

    assert selected["action"] == "GENERATE_SCRIPT"


def test_chat_service_prefers_rule_created_converse_when_rule_has_local_answer():
    service = ChatService()
    project = SimpleNamespace(workflow_stage="created", stage_status="idle")
    llm_plan = {"action": "CONVERSE", "assistant_content": ""}
    rule_plan = {
        "action": "CONVERSE",
        "affected_stage": "",
        "affected_frame_ids": [],
        "assistant_content": "你好，我在。你可以直接告诉我想做什么产品的带货视频。",
    }

    selected = service._prefer_rule_script_generation_for_created_project(project, llm_plan, rule_plan)

    assert selected["assistant_content"].startswith("你好")


def test_streaming_script_generation_does_not_restore_legacy_button_copy():
    chat_source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")
    stream_section = chat_source[
        chat_source.index("async def handle_message_stream"):
        chat_source.index("def _prefer_rule_script_generation_for_created_project")
    ]

    assert "确认并生成图片" not in stream_section
    assert "剧本已生成完成" not in stream_section
    assert "full_content = text" in stream_section


def test_streaming_route_wraps_generator_exceptions_as_sse_error_events():
    controller_source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    route_section = controller_source[
        controller_source.index("async def chat_stream"):
        controller_source.index("@router.post(\"/projects/{project_id}/pending-actions")
    ]

    assert "async def stream_events()" in route_section
    assert 'yield f"event: error' in route_section
    assert "except Exception as exc" in route_section


def test_converse_stream_yields_llm_chunks_without_collecting_first():
    chat_source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")
    stream_section = chat_source[
        chat_source.index('if action == "CONVERSE"'):
        chat_source.index("# 5.", chat_source.index('if action == "CONVERSE"'))
    ]

    assert "chunks = []" not in stream_section
    assert "for chunk in llm_agent_service.stream_converse" in stream_section
    assert 'yield sse("token", {"content": chunk})' in stream_section


def test_rule_agent_has_created_stage_greeting_response_without_external_llm():
    project = SimpleNamespace(workflow_stage="created", stage_status="idle")

    plan = workflow_agent_service.plan(project, [], "你好")

    assert plan["action"] == "CONVERSE"
    assert plan["assistant_content"]
    assert "产品" in plan["assistant_content"]


def test_no_project_intent_does_not_create_project_for_greeting():
    from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message

    result = classify_no_project_message("你好")

    assert result["action"] == "CONVERSE"
    assert result["should_create_project"] is False
    assert "创建项目" in result["assistant_content"]


def test_no_project_intent_creates_project_for_video_generation_request():
    from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message

    result = classify_no_project_message("生成一个电竞耳机带货视频")

    assert result["action"] == "CREATE_PROJECT"
    assert result["should_create_project"] is True


def test_entry_chat_stream_uses_llm_for_no_project_conversation():
    controller_source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    route_section = controller_source[
        controller_source.index("async def chat_entry_stream"):
        controller_source.index("@router.post(\"/projects/{project_id}/pending-actions")
    ]

    assert "llm_agent_service.stream_entry_converse" in route_section
    assert "intent.get(\"assistant_content\")" not in route_section
