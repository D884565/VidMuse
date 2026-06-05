from types import SimpleNamespace
from pathlib import Path

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

    service = LLMAgentService()

    assert service._infer_affected_stage("GENERATE_IMAGES") == "image"
    assert service._infer_affected_stage("GENERATE_VIDEO") == "video"
    assert service._infer_affected_stage("REGENERATE_TTS") == "video"


def test_chat_service_has_real_generation_action_branches():
    source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")

    assert 'plan["action"] == "GENERATE_IMAGES"' in source
    assert 'plan["action"] == "GENERATE_VIDEO"' in source
    assert 'plan["action"] == "REGENERATE_TTS"' in source
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
