"""规则优先的工作流 Agent：将用户自然语言映射为可执行的项目动作。"""
from __future__ import annotations

import re


class WorkflowAgentService:
    """将用户自然语言映射为可执行的工作流动作。

    第一版按规则优先：确认、生成、重生成这类高频意图不需要 LLM。
    只有规则无法判断时才返回澄清动作，避免误触发昂贵的视频生成。
    """

    def plan(self, project, frames: list, content: str, frame_id: int | None = None) -> dict:
        """根据用户输入和项目当前阶段，返回一个动作计划。"""
        text = (content or "").strip()
        stage = getattr(project, "workflow_stage", None) or "created"
        selected_frame_ids = self._resolve_frame_ids(frames, text, frame_id)

        # 优先判断：用户想重生成某张图片
        if self._wants_image_regeneration(text, selected_frame_ids):
            return self._plan(
                "REGENERATE_FRAME_IMAGE",
                affected_stage="image",
                affected_frame_ids=selected_frame_ids,
                next_stage="image",
                assistant_content="我会按你的要求重生成对应分镜图片，视频阶段会先标记为失效。",
            )

        # 判断确认意图：根据当前阶段分发到不同的确认动作
        if self._has_confirm_intent(text):
            if stage == "script" and self._mentions_image_or_next(text):
                return self._plan(
                    "CONFIRM_SCRIPT_AND_GENERATE_IMAGES",
                    affected_stage="script",
                    next_stage="image",
                    assistant_content="剧本已确认，我会开始生成分镜图片。",
                )
            if stage == "image" and self._mentions_video_or_next(text):
                return self._plan(
                    "CONFIRM_IMAGES_AND_GENERATE_VIDEO",
                    affected_stage="image",
                    next_stage="video",
                    assistant_content="图片已确认，我会开始生成最终视频。",
                )
            if stage == "video":
                return self._plan(
                    "CONFIRM_VIDEO",
                    affected_stage="video",
                    next_stage="completed",
                    assistant_content="视频已确认完成。",
                )

        # 判断生成剧本意图
        if stage in {"created", "script"} and self._mentions_script_generation(text):
            return self._plan(
                "GENERATE_SCRIPT",
                affected_stage="script",
                next_stage="script",
                assistant_content="我会开始生成剧本方案。",
            )

        # 剧本阶段的其他文字输入视为剧本修改要求
        if stage == "script" and text:
            return self._plan(
                "UPDATE_SCRIPT_TEXT",
                affected_stage="script",
                next_stage="script",
                assistant_content="我会先记录你的剧本修改要求，并把后续图片和视频标记为需要更新。",
            )

        # 无法判断意图时，返回澄清动作
        return self._plan(
            "ASK_CLARIFYING_QUESTION",
            affected_stage=stage,
            requires_confirmation=True,
            assistant_content="你想修改剧本、重生成某张图片，还是继续推进到下一阶段？",
        )

    def _plan(
        self,
        action: str,
        *,
        affected_stage: str,
        affected_frame_ids: list[int] | None = None,
        requires_confirmation: bool = False,
        assistant_content: str,
        next_stage: str | None = None,
    ) -> dict:
        """构造标准化的动作计划字典。"""
        return {
            "action": action,
            "affected_stage": affected_stage,
            "affected_frame_ids": affected_frame_ids or [],
            "requires_confirmation": requires_confirmation,
            "assistant_content": assistant_content,
            "next_stage": next_stage,
            "estimated_cost_label": "low" if action != "CONFIRM_IMAGES_AND_GENERATE_VIDEO" else "high",
        }

    def _resolve_frame_ids(self, frames: list, text: str, frame_id: int | None) -> list[int]:
        """从文本中解析帧序号（如"第2张"），或直接使用传入的 frame_id。"""
        if frame_id:
            return [frame_id]
        match = re.search(r"第\s*(\d+)\s*[张帧个]?", text)
        if not match:
            return []
        sequence = int(match.group(1))
        return [
            getattr(frame, "id")
            for frame in frames
            if getattr(frame, "sequence", None) == sequence and getattr(frame, "id", None) is not None
        ]

    def _has_confirm_intent(self, text: str) -> bool:
        """判断用户是否表达确认意图。"""
        return any(word in text for word in ("确认", "可以", "没问题", "下一步", "继续", "通过"))

    def _mentions_image_or_next(self, text: str) -> bool:
        """判断用户是否提及图片或推进下一步。"""
        return any(word in text for word in ("图片", "这张图", "分镜图", "画面", "下一步", "继续"))

    def _mentions_video_or_next(self, text: str) -> bool:
        """判断用户是否提及视频或推进下一步。"""
        return any(word in text for word in ("视频", "成片", "下一步", "继续"))

    def _mentions_script_generation(self, text: str) -> bool:
        """判断用户是否要求生成剧本。"""
        return any(word in text for word in ("生成剧本", "开始剧本", "写剧本", "出脚本"))

    def _wants_image_regeneration(self, text: str, frame_ids: list[int]) -> bool:
        """判断用户是否要求重生成某张图片（需要同时有帧引用和图片相关词）。"""
        if not frame_ids:
            return False
        return any(word in text for word in ("图片", "这张图", "分镜图", "画面", "换成", "重生成", "不满意"))


workflow_agent_service = WorkflowAgentService()
