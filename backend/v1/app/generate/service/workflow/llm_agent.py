"""LLM 驱动的工作流 Agent：用大模型理解用户意图，输出结构化执行计划。"""
from __future__ import annotations

import json
import logging
from typing import Any

from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """你是「带货视频生成系统」的 AI 助手。你的职责是帮助用户一步步创建带货短视频，流程为：剧本 → 图片 → 视频（严格顺序，不能跳过）。

当前项目状态:
- workflow_stage: {workflow_stage}
- stage_status: {stage_status}
- dirty_stage: {dirty_stage}
- 共 {frame_count} 个分镜

{frame_summaries}

可用动作:
- GENERATE_SCRIPT: 生成/重新生成剧本脚本（当用户描述产品、提供推广需求、粘贴商品链接时使用）
- GENERATE_IMAGES: 生成/重新生成项目分镜首帧图片
- GENERATE_VIDEO: 生成/重新生成项目视频成片
- EDIT_FRAME: 修改某个分镜的内容（描述、旁白、图片提示词、视频提示词、时长等）
- REGENERATE_FRAME_IMAGE: 重新生成某个分镜的图片
- REGENERATE_FRAME_VIDEO: 重新生成某个分镜的视频
- REGENERATE_TTS: 重新生成配音音频（旁白或音色变化时使用）
- CONFIRM_AND_ADVANCE: 确认当前阶段并进入下一阶段
- CHANGE_BGM: 用户对当前背景音乐不满意，要求更换（如"换一首"、"换个BGM"、"不喜欢这个音乐"）
- CONVERSE: 与用户进行普通对话（回答问题、闲聊、讨论创意方向、解释系统功能等，不触发任何工作流操作）
- ASK_CLARIFYING: 需要用户澄清意图

决策规则:
1. 当 workflow_stage 为 created 且用户描述了产品或提供了推广需求（产品名称、链接、卖点、风格偏好等），使用 GENERATE_SCRIPT
2. 当 workflow_stage 为 created 且用户只是打招呼或问系统功能相关问题，使用 CONVERSE
3. 当用户的消息包含足够的产品信息（即使没有明确说"生成剧本"），也应使用 GENERATE_SCRIPT
4. 工作流必须按顺序进行：剧本(script) -> 图片(image) -> 视频(video)。没有剧本不能生成图片，没有图片不能生成视频
5. 当剧本生成完成后（stage_status=awaiting_review, workflow_stage=script），如果用户表示满意或说了确认类词语，使用 CONFIRM_AND_ADVANCE
6. 当图片生成完成后（stage_status=awaiting_review, workflow_stage=image），同理

重要规则:
1. 涉及生成图片/视频等昂贵操作时，needs_confirmation 必须为 true
2. 用户说"确认"、"可以"、"没问题"、"下一步"、"继续"等确认词时，needs_confirmation 可以为 false
3. 修改剧本或分镜内容时，needs_confirmation 为 false（只是记录修改）
4. target_frames 填写帧序号数组（从1开始），如 [1, 3] 表示第1和第3个分镜
5. modifications 只包含用户明确要修改的字段
6. confidence 表示你对意图判断的置信度（0-1），低于 0.5 时应使用 CONVERSE 或 ASK_CLARIFYING

严格按以下 JSON 格式输出，不要输出任何其他内容:
{{
  "action": "动作名",
  "target_frames": [帧序号列表],
  "modifications": {{
    "字段名": "新值"
  }},
  "message": "给用户的回复",
  "needs_confirmation": true/false,
  "confidence": 0.95
}}"""

SYSTEM_PROMPT_TEMPLATE += """

Project regeneration actions:
- REGENERATE_PROJECT_ALL: regenerate script, images, and video from scratch.
- REGENERATE_IMAGES_AND_VIDEO: keep the script unchanged, regenerate all images and video.
- REGENERATE_VIDEO_ONLY: keep script and images unchanged, regenerate video only.
Use needs_confirmation=true for all three regeneration actions unless the user is explicitly confirming a pending action.
"""

VALID_ACTIONS = {
    "GENERATE_SCRIPT",
    "GENERATE_IMAGES",
    "GENERATE_VIDEO",
    "EDIT_FRAME",
    "REGENERATE_FRAME_IMAGE",
    "REGENERATE_FRAME_VIDEO",
    "REGENERATE_TTS",
    "REGENERATE_PROJECT_ALL",
    "REGENERATE_IMAGES_AND_VIDEO",
    "REGENERATE_VIDEO_ONLY",
    "CONFIRM_AND_ADVANCE",
    "CHANGE_BGM",
    "CONVERSE",
    "ASK_CLARIFYING",
}

VALID_MODIFICATION_FIELDS = {
    "description",
    "narration",
    "image_prompt",
    "video_prompt",
    "duration",
    "voice_type",
    "voice_style",
}

CONFIDENCE_THRESHOLD = 0.7

# 最近 N 条消息作为 LLM context
MAX_HISTORY_MESSAGES = 10


class LLMAgentService:
    """LLM 驱动的意图理解和动作规划服务。"""

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            if VolcanoLLM is None:
                raise RuntimeError("VolcanoLLM 不可用")
            self._llm = VolcanoLLM(key=None, model_name=None)
        return self._llm

    def plan(
        self,
        project,
        frames: list,
        content: str,
        frame_id: int | None = None,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """用 LLM 分析用户消息，返回结构化执行计划。"""
        system_prompt = self._build_system_prompt(project, frames)
        messages = self._build_messages(system_prompt, conversation_history, content)

        try:
            response = self._call_llm(messages)
            plan = self._parse_response(response)
            plan = self._validate_and_normalize(plan, frames, frame_id)
            return plan
        except Exception as exc:
            logger.warning("LLM Agent 调用失败，降级到规则引擎: %s", exc)
            return None  # 返回 None 让调用方降级

    def _build_system_prompt(self, project, frames: list) -> str:
        """构建包含项目状态上下文的 system prompt。"""
        workflow_stage = getattr(project, "workflow_stage", None) or "created"
        stage_status = getattr(project, "stage_status", None) or "idle"
        dirty_stage = getattr(project, "dirty_stage", None) or "无"

        frame_summaries = ""
        if frames:
            lines = ["分镜列表:"]
            for f in frames:
                seq = getattr(f, "sequence", "?")
                desc = getattr(f, "description", "") or "无描述"
                status = getattr(f, "status", 0)
                dirty = getattr(f, "dirty", 0)
                status_map = {0: "待处理", 1: "生成中", 2: "已完成", 3: "失败"}
                status_text = status_map.get(status, "未知")
                dirty_text = " [需重新确认]" if dirty else ""
                lines.append(f"  第{seq}个: {desc[:50]}... (状态: {status_text}{dirty_text})")
            frame_summaries = "\n".join(lines)

        return SYSTEM_PROMPT_TEMPLATE.format(
            workflow_stage=workflow_stage,
            stage_status=stage_status,
            dirty_stage=dirty_stage,
            frame_count=len(frames),
            frame_summaries=frame_summaries or "(暂无分镜)",
        )

    def _build_messages(
        self,
        system_prompt: str,
        conversation_history: list[dict] | None,
        current_message: str,
    ) -> list[dict]:
        """构建发送给 LLM 的消息列表。"""
        messages = [{"role": "system", "content": system_prompt}]

        # 添加最近的对话历史
        if conversation_history:
            recent = conversation_history[-MAX_HISTORY_MESSAGES:]
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ("user", "assistant"):
                    messages.append({"role": role, "content": content})

        # 添加当前用户消息
        messages.append({"role": "user", "content": current_message})
        return messages

    def _call_llm(self, messages: list[dict]) -> str:
        """调用 LLM 获取响应文本。"""
        request = ChatRequest(
            messages=[ChatMessage(**msg) for msg in messages],
            temperature=0.1,  # 低温度确保输出稳定
            max_tokens=500,
        )
        response = self.llm._chat(request)
        return response.content

    def _parse_response(self, content: str) -> dict:
        """解析 LLM 返回的 JSON 执行计划。"""
        # 尝试提取 JSON（处理 LLM 可能包裹 markdown 代码块的情况）
        text = content.strip()
        if text.startswith("```"):
            # 去掉 ```json 和 ```
            lines = text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines).strip()

        return json.loads(text)

    def _validate_and_normalize(
        self,
        plan: dict,
        frames: list,
        frame_id: int | None,
    ) -> dict:
        """验证并规范化 LLM 输出的执行计划。"""
        action = plan.get("action", "").upper()
        if action not in VALID_ACTIONS:
            action = "ASK_CLARIFYING"

        confidence = float(plan.get("confidence", 0))
        if confidence < CONFIDENCE_THRESHOLD:
            action = "ASK_CLARIFYING"

        # 规范化 target_frames: 将帧序号转为帧 ID
        target_frame_ids = []
        raw_frames = plan.get("target_frames", [])
        if frame_id and not raw_frames:
            target_frame_ids = [frame_id]
        elif raw_frames:
            seq_to_id = {getattr(f, "sequence", None): getattr(f, "id", None) for f in frames}
            for seq in raw_frames:
                fid = seq_to_id.get(int(seq))
                if fid:
                    target_frame_ids.append(fid)

        # 如果有显式 frame_id 且 LLM 没指定帧，用 frame_id
        if frame_id and not target_frame_ids:
            target_frame_ids = [frame_id]

        # 规范化 modifications
        modifications = plan.get("modifications", {})
        if isinstance(modifications, dict):
            modifications = {
                k: v for k, v in modifications.items()
                if k in VALID_MODIFICATION_FIELDS
            }
        else:
            modifications = {}

        # 确定受影响的阶段
        affected_stage = self._infer_affected_stage(action)

        return {
            "action": action,
            "affected_stage": affected_stage,
            "affected_frame_ids": target_frame_ids,
            "modifications": modifications,
            "assistant_content": plan.get("message", ""),
            "needs_confirmation": plan.get("needs_confirmation", True),
            "confidence": confidence,
            "next_stage": affected_stage,
            "estimated_cost_label": self._estimate_cost_label(action),
            "requires_confirmation": plan.get("needs_confirmation", True),
        }

    def _infer_affected_stage(self, action: str) -> str:
        """根据动作类型推断受影响的阶段。"""
        stage_map = {
            "GENERATE_SCRIPT": "script",
            "GENERATE_IMAGES": "image",
            "GENERATE_VIDEO": "video",
            "EDIT_FRAME": "script",
            "REGENERATE_FRAME_IMAGE": "image",
            "REGENERATE_FRAME_VIDEO": "video",
            "REGENERATE_TTS": "video",
            "REGENERATE_PROJECT_ALL": "script",
            "REGENERATE_IMAGES_AND_VIDEO": "image",
            "REGENERATE_VIDEO_ONLY": "video",
            "CONFIRM_AND_ADVANCE": "",  # 由调用方根据当前阶段决定
            "CONVERSE": "",
            "ASK_CLARIFYING": "",
        }
        return stage_map.get(action, "")

    def _estimate_cost_label(self, action: str) -> str:
        """估算操作成本等级。"""
        high_cost = {
            "REGENERATE_FRAME_IMAGE",
            "REGENERATE_FRAME_VIDEO",
            "GENERATE_SCRIPT",
            "GENERATE_IMAGES",
            "GENERATE_VIDEO",
            "REGENERATE_TTS",
            "REGENERATE_PROJECT_ALL",
            "REGENERATE_IMAGES_AND_VIDEO",
            "REGENERATE_VIDEO_ONLY",
        }
        return "high" if action in high_cost else "low"

    def stream_converse(
        self,
        project,
        frames: list,
        content: str,
        conversation_history: list[dict] | None = None,
    ):
        """生成流式对话回复（纯文本，非 JSON）。用于 CONVERSE 动作。"""
        converse_prompt = self._build_converse_prompt(project, frames)
        messages = self._build_messages(converse_prompt, conversation_history, content)
        request = ChatRequest(
            messages=[ChatMessage(**msg) for msg in messages],
            temperature=0.7,
            max_tokens=1000,
        )
        for chunk in self.llm.stream_chat(request):
            yield chunk

    def stream_entry_converse(self, content: str):
        """Stream ordinary conversation before a project exists."""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是带货视频生成系统的 AI 助手。当前还没有创建视频项目。"
                    "请像正常聊天一样回答用户问题，可以解释系统能力、讨论创意、回答闲聊。"
                    "不要擅自创建项目，不要输出 JSON；如果用户想开始做视频，引导他说清楚产品和目标。"
                ),
            },
            {"role": "user", "content": content},
        ]
        request = ChatRequest(
            messages=[ChatMessage(**msg) for msg in messages],
            temperature=0.7,
            max_tokens=800,
        )
        for chunk in self.llm.stream_chat(request):
            yield chunk

    def _build_converse_prompt(self, project, frames: list) -> str:
        """构建对话模式的 system prompt（非 JSON 输出）。"""
        workflow_stage = getattr(project, "workflow_stage", None) or "created"
        stage_status = getattr(project, "stage_status", None) or "idle"
        frame_count = len(frames)

        return f"""你是「带货视频生成系统」的 AI 助手。你正在和用户讨论视频项目。

当前项目状态:
- 阶段: {workflow_stage}（{stage_status}）
- 共 {frame_count} 个分镜

你可以：
- 回答用户关于项目的问题
- 讨论创意方向和风格偏好
- 解释系统功能和操作方式
- 给出修改建议

用自然、友好的中文回复。不要输出 JSON 格式。"""


llm_agent_service = LLMAgentService()
