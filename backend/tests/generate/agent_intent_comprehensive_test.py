# -*- coding: utf-8 -*-
"""
意图识别完整测试

覆盖场景：
1. 无关消息（打招呼、闲聊、问功能）
2. 任务推动（确认当前阶段、推进到下一阶段）
3. LLM 降级逻辑（_fallback_project_intent）
4. 计划规范化（_normalize_plan）
5. 入口意图识别（entry_intent.py）
6. 状态机边界
7. 重试协调器
"""
from types import SimpleNamespace

import pytest

from backend.v1.app.generate.service.chat.intent_service import (
    _fallback_project_intent,
    _normalize_plan,
)


# ============ 1. LLM 降级逻辑 ============

class TestFallbackLogic:
    """LLM 失败时的降级规则（intent_service.py 内置的极简降级）"""

    def test_fallback_confirm_script(self):
        result = _fallback_project_intent("确认", "script", [])
        assert result["action"] == "CONFIRM_AND_ADVANCE"

    def test_fallback_confirm_image(self):
        result = _fallback_project_intent("可以", "image", [])
        assert result["action"] == "CONFIRM_AND_ADVANCE"

    def test_fallback_confirm_video(self):
        result = _fallback_project_intent("没问题", "video", [])
        assert result["action"] == "CONFIRM_AND_ADVANCE"

    def test_fallback_converse(self):
        result = _fallback_project_intent("你好", "created", [])
        assert result["action"] == "CONVERSE"

    def test_fallback_empty(self):
        result = _fallback_project_intent("", "created", [])
        assert result["action"] == "CONVERSE"

    def test_fallback_non_confirm_in_script(self):
        """非确认消息在 script 阶段走对话"""
        result = _fallback_project_intent("这个镜头改一下", "script", [])
        assert result["action"] == "CONVERSE"

    def test_fallback_non_confirm_in_image(self):
        result = _fallback_project_intent("图片不好看", "image", [])
        assert result["action"] == "CONVERSE"


# ============ 2. 计划规范化 ============

class TestNormalizePlan:
    """_normalize_plan 的验证和规范化逻辑"""

    def test_invalid_action_becomes_clarifying(self):
        result = _normalize_plan({"action": "INVALID_ACTION", "confidence": 0.9})
        assert result["action"] == "ASK_CLARIFYING"

    def test_low_confidence_becomes_clarifying(self):
        result = _normalize_plan({"action": "GENERATE_SCRIPT", "confidence": 0.2})
        assert result["action"] == "ASK_CLARIFYING"

    def test_valid_plan_passes_through(self):
        result = _normalize_plan({
            "action": "REGENERATE_FRAME_IMAGE",
            "affected_frame_ids": [1, 2],
            "modifications": {},
            "needs_confirmation": True,
            "message": "好的",
            "confidence": 0.9,
        })
        assert result["action"] == "REGENERATE_FRAME_IMAGE"
        assert result["affected_frame_ids"] == [1, 2]

    def test_regeneration_actions_are_valid(self):
        """验证项目级重跑 action 不会被降级为 ASK_CLARIFYING"""
        for action in ["REGENERATE_PROJECT_ALL", "REGENERATE_IMAGES_AND_VIDEO", "REGENERATE_VIDEO_ONLY"]:
            result = _normalize_plan({"action": action, "confidence": 0.9})
            assert result["action"] == action, f"{action} should be valid"

    def test_confirm_and_advance_is_valid(self):
        result = _normalize_plan({"action": "CONFIRM_AND_ADVANCE", "confidence": 0.9})
        assert result["action"] == "CONFIRM_AND_ADVANCE"

    def test_frame_seq_to_id_conversion(self):
        frames = [
            SimpleNamespace(id=10, sequence=1),
            SimpleNamespace(id=20, sequence=2),
            SimpleNamespace(id=30, sequence=3),
        ]
        result = _normalize_plan({
            "action": "REGENERATE_FRAME_IMAGE",
            "target_frames": [2, 3],
            "confidence": 0.9,
        }, frames=frames)
        assert result["affected_frame_ids"] == [20, 30]


# ============ 3. 入口意图识别 ============

class TestEntryIntent:
    """项目创建前的入口意图识别"""

    def test_greeting_no_project(self):
        from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message
        result = classify_no_project_message("你好")
        assert result["should_create_project"] is False

    def test_video_request_creates_project(self):
        from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message
        result = classify_no_project_message("生成一个电竞耳机带货视频")
        assert result["should_create_project"] is True

    def test_functional_question_no_project(self):
        from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message
        result = classify_no_project_message("这个系统怎么用")
        assert result["should_create_project"] is False

    def test_url_triggers_project_creation(self):
        from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message
        result = classify_no_project_message("https://item.jd.com/123")
        assert result["should_create_project"] is True


# ============ 4. 状态机边界 ============

class TestStateMachineEdgeCases:
    """工作流状态机的边界情况"""

    def test_confirm_wrong_stage(self):
        from backend.v1.app.generate.service.workflow.state import GenerationWorkflowService
        p = SimpleNamespace(workflow_stage="script", stage_status="awaiting_review",
                           dirty_stage=None, script_confirmed_at=None,
                           images_confirmed_at=None, video_confirmed_at=None,
                           last_task_id=None)
        with pytest.raises(ValueError, match="cannot confirm"):
            GenerationWorkflowService().confirm_stage(p, "image")

    def test_confirm_non_reviewable_status(self):
        from backend.v1.app.generate.service.workflow.state import GenerationWorkflowService
        p = SimpleNamespace(workflow_stage="script", stage_status="running",
                           dirty_stage=None, script_confirmed_at=None,
                           images_confirmed_at=None, video_confirmed_at=None,
                           last_task_id=None)
        with pytest.raises(ValueError, match="not reviewable"):
            GenerationWorkflowService().confirm_stage(p, "script")

    def test_invalidate_from_image_preserves_script(self):
        from backend.v1.app.generate.service.workflow.state import GenerationWorkflowService
        from datetime import datetime, timezone
        p = SimpleNamespace(workflow_stage="video", stage_status="awaiting_review",
                           dirty_stage=None, script_confirmed_at=None,
                           images_confirmed_at=None, video_confirmed_at=None,
                           last_task_id=None)
        p.script_confirmed_at = datetime.now(timezone.utc)
        p.images_confirmed_at = datetime.now(timezone.utc)
        p.video_confirmed_at = datetime.now(timezone.utc)
        GenerationWorkflowService().invalidate_from(p, "image")
        assert p.workflow_stage == "script"
        assert p.stage_status == "confirmed"
        assert p.dirty_stage == "image"
        assert p.script_confirmed_at is not None

    def test_invalidate_from_script_clears_all(self):
        from backend.v1.app.generate.service.workflow.state import GenerationWorkflowService
        from datetime import datetime, timezone
        p = SimpleNamespace(workflow_stage="video", stage_status="awaiting_review",
                           dirty_stage=None, script_confirmed_at=None,
                           images_confirmed_at=None, video_confirmed_at=None,
                           last_task_id=None)
        p.script_confirmed_at = datetime.now(timezone.utc)
        p.images_confirmed_at = datetime.now(timezone.utc)
        p.video_confirmed_at = datetime.now(timezone.utc)
        GenerationWorkflowService().invalidate_from(p, "script")
        assert p.workflow_stage == "script"
        assert p.stage_status == "idle"
        assert p.dirty_stage == "script"
        assert p.script_confirmed_at is None


# ============ 5. 重试协调器 ============

class TestRetryCoordinator:
    """断点续传和重试逻辑"""

    def test_no_task_resume_point(self):
        from unittest.mock import MagicMock, patch
        from backend.v1.app.generate.service.generateUtils.retry_coordinator import RetryCoordinator
        coordinator = RetryCoordinator()
        mock_db = MagicMock()
        with patch("backend.v1.app.generate.service.generateUtils.retry_coordinator.generation_task_tracker") as mt:
            mt.get_latest_task.return_value = None
            result = coordinator.determine_resume_point(mock_db, 1)
            assert result.stage == "start"
            assert result.frames_to_retry == []

    def test_failed_image_resume_point(self):
        from unittest.mock import MagicMock, patch
        from backend.v1.app.generate.service.generateUtils.retry_coordinator import RetryCoordinator
        coordinator = RetryCoordinator()
        mock_db = MagicMock()
        with patch("backend.v1.app.generate.service.generateUtils.retry_coordinator.generation_task_tracker") as mt:
            mt.get_latest_task.return_value = {"task_id": "gen_t1", "status": "failed", "current_stage": "image"}
            mt.get_failed_frames.return_value = [2, 3]
            result = coordinator.determine_resume_point(mock_db, 1)
            assert result.stage == "image"
            assert result.frames_to_retry == [2, 3]

    def test_failed_video_resume_point(self):
        from unittest.mock import MagicMock, patch
        from backend.v1.app.generate.service.generateUtils.retry_coordinator import RetryCoordinator
        coordinator = RetryCoordinator()
        mock_db = MagicMock()
        with patch("backend.v1.app.generate.service.generateUtils.retry_coordinator.generation_task_tracker") as mt:
            mt.get_latest_task.return_value = {"task_id": "gen_t2", "status": "failed", "current_stage": "video"}
            mt.get_failed_frames.return_value = [1]
            result = coordinator.determine_resume_point(mock_db, 1)
            assert result.stage == "video"
            assert result.frames_to_retry == [1]

    def test_prepare_retry_with_frames(self):
        from unittest.mock import MagicMock, patch
        from backend.v1.app.generate.service.generateUtils.retry_coordinator import RetryCoordinator
        coordinator = RetryCoordinator()
        mock_db = MagicMock()
        with patch("backend.v1.app.generate.service.generateUtils.retry_coordinator.generation_task_tracker") as mt:
            mt.create_task.return_value = "gen_new"
            task_id, frames = coordinator.prepare_retry(mock_db, 1, stage="image", frame_ids=[2, 3])
            assert task_id == "gen_new"
            assert frames == [2, 3]


# ============ 6. ChatService action 分支覆盖 ============

class TestChatServiceActionCoverage:
    """验证 chat_service.py 覆盖了所有 intent_service 返回的 action"""

    def test_handle_message_covers_all_actions(self):
        """检查 handle_message 的 action 分支覆盖"""
        from pathlib import Path
        source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")
        # 必须覆盖的 action
        required_actions = [
            "GENERATE_SCRIPT",
            "CONFIRM_AND_ADVANCE",
            "GENERATE_IMAGES",
            "GENERATE_VIDEO",
            "EDIT_FRAME",
            "REGENERATE_FRAME_IMAGE",
            "REGENERATE_FRAME_VIDEO",
            "REGENERATE_TTS",
            "PROJECT_REGENERATION_ACTIONS",
            "CHANGE_BGM",
            "CONVERSE",
            "ASK_CLARIFYING",
        ]
        for action in required_actions:
            assert action in source, f"Missing action branch: {action}"

    def test_no_legacy_agent_references(self):
        """确认 chat_service.py 不再引用已删除的 agent 模块"""
        from pathlib import Path
        source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")
        assert "workflow_agent_service" not in source
        assert "workflow.agent" not in source
        assert "llm_agent" not in source

    def test_no_dead_action_branches(self):
        """确认已删除的死分支不在代码中"""
        from pathlib import Path
        source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")
        assert "CONFIRM_SCRIPT_AND_GENERATE_IMAGES" not in source
        assert "CONFIRM_IMAGES_AND_GENERATE_VIDEO" not in source
        assert "REGENERATE_FRAME_IMAGE_LEGACY" not in source
        assert "UPDATE_SCRIPT_TEXT" not in source
        # CONFIRM_VIDEO 作为独立分支不应存在（已合并到 CONFIRM_AND_ADVANCE）
        # 但 CONFIRM_VIDEO 可能出现在其他上下文中，所以只检查 action 分支
        assert 'action == "CONFIRM_VIDEO"' not in source
