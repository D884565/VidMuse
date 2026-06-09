# -*- coding: utf-8 -*-
"""
统一意图识别服务

整合入口对话和项目内对话的意图识别，
使用LLM理解用户意图，替代硬编码规则。

放在generate/chat下，作为独立的意图识别工具。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage
from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message

logger = logging.getLogger(__name__)
SUPPORTED_EDIT_FIELDS = {"description", "narration", "image_prompt", "video_prompt", "duration", "price"}


# ============ 入口对话意图识别 ============

ENTRY_SYSTEM_PROMPT = """你是一个意图分类器。判断用户消息是否要创建视频项目。

## 输出格式（严格JSON）
{
  "should_create_project": true/false,
  "reason": "判断理由"
}

## 规则
1. 用户明确表达要生成/制作/创建视频、带货视频、广告、宣传片等 → true
2. 用户粘贴了商品链接 → true
3. 用户只是打招呼、问问题、闲聊 → false
4. 不确定时 → false（宁可漏判，不要误判）

## 示例
- "你好" → {"should_create_project": false, "reason": "打招呼"}
- "帮我生成一个耳机带货视频" → {"should_create_project": true, "reason": "明确要求生成视频"}
- "https://item.jd.com/123" → {"should_create_project": true, "reason": "商品链接"}
- "这个功能怎么用" → {"should_create_project": false, "reason": "询问功能"}
- "创作一个护肤品宣传片" → {"should_create_project": true, "reason": "要求创作宣传片"}
"""


def classify_entry_intent(content: str) -> dict:
    """
    入口对话意图识别（LLM驱动）

    替代原有的硬编码规则 entry_intent.py

    Args:
        content: 用户消息

    Returns:
        {"should_create_project": bool, "reason": str}
    """
    fallback = _fallback_entry_intent(content)
    try:
        llm = VolcanoLLM(key=None, model_name=None)
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=ENTRY_SYSTEM_PROMPT),
                ChatMessage(role="user", content=content),
            ],
            temperature=0.1,
            max_tokens=100,
        )
        response = llm._chat(request)
        result = json.loads(response.content.strip())
        normalized = {
            "should_create_project": result.get("should_create_project", False),
            "reason": result.get("reason", ""),
        }
        if fallback.get("should_create_project") and not normalized["should_create_project"]:
            return fallback
        return normalized
    except Exception as e:
        logger.warning(f"LLM入口意图识别失败，降级到规则: {e}")
        return fallback


def _fallback_entry_intent(content: str) -> dict:
    """降级规则：LLM失败时复用统一入口判定。"""
    result = classify_no_project_message(content)
    return {
        "should_create_project": result.get("should_create_project", False),
        "reason": "entry_intent_fallback",
    }


# ============ 项目内意图识别 ============

PROJECT_SYSTEM_PROMPT_TEMPLATE = """你是「带货视频生成系统」的意图分类器。根据用户消息和项目状态，输出结构化的执行计划。

## 当前项目状态
- workflow_stage: {workflow_stage}
- stage_status: {stage_status}
- 分镜数: {frame_count}

{frame_summaries}

## 可用动作
- GENERATE_SCRIPT: 生成剧本
- GENERATE_IMAGES: 生成图片
- GENERATE_VIDEO: 生成视频
- EDIT_FRAME: 修改分镜内容
- REGENERATE_FRAME_IMAGE: 重新生成某张图片
- REGENERATE_FRAME_VIDEO: 重新生成某个视频
- REGENERATE_TTS: 重新生成配音
- CONFIRM_AND_ADVANCE: 确认当前阶段并推进
- CHANGE_BGM: 更换背景音乐
- CONVERSE: 普通对话
- ASK_CLARIFYING: 需要澄清
- REGENERATE_PROJECT_ALL: 项目级重跑——从剧本开始全部重新生成（需确认）
- REGENERATE_IMAGES_AND_VIDEO: 保留剧本，重新生成图片和视频（需确认）
- REGENERATE_VIDEO_ONLY: 保留剧本和图片，仅重新生成视频（需确认）

## 输出格式（严格JSON）
{{
  "action": "动作名",
  "affected_frame_ids": [帧ID列表],
  "modifications": {{}},
  "needs_confirmation": true/false,
  "assistant_content": "回复用户的内容",
  "confidence": 0.9
}}

## 规则
1. 用户说"确认/可以/继续/下一步" → CONFIRM_AND_ADVANCE
2. 用户描述了产品需求 → GENERATE_SCRIPT
3. 用户要求修改分镜内容(描述/旁白/提示词) → EDIT_FRAME
4. 用户提到"第X张图/分镜"且表达不满意/要改/重做 → REGENERATE_FRAME_IMAGE
5. 用户提到"第X个视频/片段"且表达不满意/要改/重做 → REGENERATE_FRAME_VIDEO
6. 普通聊天/问答 → CONVERSE
7. 不确定 → ASK_CLARIFYING
8. 用户要求全部重跑/从头重新生成 → REGENERATE_PROJECT_ALL
9. 用户要求保留剧本但重做图片和视频 → REGENERATE_IMAGES_AND_VIDEO
10. 用户要求只重做视频 → REGENERATE_VIDEO_ONLY

## EDIT_FRAME 的 modifications 格式

EDIT_FRAME 有两种修改模式：

### 模式1：精确替换（推荐，用于替换具体文本）
格式：{{"字段名": {{"replace": ["旧文本", "新文本"]}}}}
- 用户说"把男生改为女生" → 在所有包含"男生"的字段中替换：
  {{"description": {{"replace": ["男生", "女生"]}}, "image_prompt": {{"replace": ["男生", "女生"]}}, "narration": {{"replace": ["男生", "女生"]}}}}
- 用户说"价格改成109元" → 在所有包含"89元"的字段中替换：
  {{"description": {{"replace": ["89元", "109元"]}}, "image_prompt": {{"replace": ["89元", "109元"]}}}}
- 用户说"品牌名改成华为" → 在所有包含原品牌名的字段中替换

### 模式2：整段覆写（仅用于语气/风格调整等无法精确替换的场景）
格式：{{"字段名": "新内容"}}
- 用户说"旁白语气改活泼点" → 整段覆写 narration
- 用户说"描述写得更详细点" → 整段覆写 description

### 替换规则
1. 必须同时修改所有包含旧文本的字段（description、image_prompt、video_prompt、narration、subtitle_text）
2. 不要修改不包含旧文本的字段
3. 如果用户只说"改价格"但没说改成多少，在 assistant_content 中询问具体价格
4. 如果用户说"修改描述"但没给具体内容，在 assistant_content 中询问

## 重要提示
- 包含"第X张"、"第X个"并带有修改意图时，必须选择对应的REGENERATE或EDIT动作
- "不满意"、"不好看"、"换掉"、"重新生成"都是修改意图，用REGENERATE
- "修改"、"编辑"、"改一下"、"调整"是编辑意图，用EDIT_FRAME
- EDIT_FRAME 优先用精确替换模式，只在语气/风格调整时用整段覆写
- 如果用户说"修改描述"但没给新值，仍然用EDIT_FRAME，在assistant_content中询问具体修改内容
"""


def classify_project_intent(
    content: str,
    workflow_stage: str = "created",
    stage_status: str = "idle",
    frames: list = None,
    conversation_history: list = None,
) -> dict:
    """
    项目内意图识别（LLM驱动）

    使用 LLM 理解用户意图，输出结构化执行计划。

    Args:
        content: 用户消息
        workflow_stage: 当前工作流阶段
        stage_status: 阶段状态
        frames: 分镜列表
        conversation_history: 对话历史

    Returns:
        {
            "action": str,
            "affected_frame_ids": list,
            "modifications": dict,
            "needs_confirmation": bool,
            "assistant_content": str,
            "confidence": float
        }
    """
    # 构建frame摘要
    frame_summaries = ""
    if frames:
        lines = ["分镜列表:"]
        for f in frames:
            seq = getattr(f, "sequence", "?")
            desc = getattr(f, "description", "") or "无描述"
            status = getattr(f, "status", 0)
            dirty = getattr(f, "dirty", 0)
            status_map = {0: "待处理", 1: "生成中", 2: "已完成", 3: "失败"}
            dirty_mark = " [已修改待重生成]" if dirty else ""
            lines.append(f"  第{seq}个(id={f.id}): {desc[:50]}... ({status_map.get(status, '未知')}{dirty_mark})")
        frame_summaries = "\n".join(lines)

    system_prompt = PROJECT_SYSTEM_PROMPT_TEMPLATE.format(
        workflow_stage=workflow_stage,
        stage_status=stage_status,
        frame_count=len(frames) if frames else 0,
        frame_summaries=frame_summaries or "(暂无分镜)",
    )

    # 构建消息
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        for msg in conversation_history[-10:]:
            role = msg.get("role", "user")
            msg_content = msg.get("content", "")
            if msg_content and role in ("user", "assistant"):
                messages.append({"role": role, "content": msg_content})
    messages.append({"role": "user", "content": content})

    try:
        llm = VolcanoLLM(key=None, model_name=None)
        request = ChatRequest(
            messages=[ChatMessage(**m) for m in messages],
            temperature=0.1,
            max_tokens=500,
        )
        response = llm._chat(request)
        plan = json.loads(response.content.strip())
        normalized = _normalize_plan(plan, frames)
        return _postprocess_project_plan(normalized, content, frames)
    except Exception as e:
        logger.warning(f"LLM项目意图识别失败，降级到规则: {e}")
        return _fallback_project_intent(content, workflow_stage, frames)


def _normalize_plan(plan: dict, frames: list = None) -> dict:
    """规范化LLM返回的计划"""
    valid_actions = {
        "GENERATE_SCRIPT", "GENERATE_IMAGES", "GENERATE_VIDEO",
        "EDIT_FRAME", "REGENERATE_FRAME_IMAGE", "REGENERATE_FRAME_VIDEO",
        "REGENERATE_TTS", "CONFIRM_AND_ADVANCE", "CHANGE_BGM",
        "CONVERSE", "ASK_CLARIFYING",
        "REGENERATE_PROJECT_ALL", "REGENERATE_IMAGES_AND_VIDEO", "REGENERATE_VIDEO_ONLY",
    }

    action = plan.get("action", "ASK_CLARIFYING").upper()
    if action not in valid_actions:
        action = "ASK_CLARIFYING"

    confidence = float(plan.get("confidence", 0))
    if confidence < 0.5:
        action = "ASK_CLARIFYING"

    # 转换帧序号为帧ID
    affected_frame_ids = plan.get("affected_frame_ids", [])
    if frames and not affected_frame_ids:
        target_frames = plan.get("target_frames", [])
        if target_frames:
            seq_to_id = {getattr(f, "sequence", None): getattr(f, "id", None) for f in frames}
            affected_frame_ids = [seq_to_id[int(s)] for s in target_frames if int(s) in seq_to_id]

    return {
        "action": action,
        "affected_frame_ids": affected_frame_ids,
        "modifications": plan.get("modifications", {}),
        "needs_confirmation": plan.get("needs_confirmation", True),
        "assistant_content": plan.get("message", plan.get("assistant_content", "")),
        "confidence": confidence,
    }


def _fallback_project_edit_intent(content: str, frames: list = None) -> dict | None:
    text = (content or "").strip()
    if not text or not frames:
        return None

    if not any(keyword in text for keyword in ("改", "调", "换")):
        return None

    requested_prices = []
    token = ""
    for char in text:
        if char.isdigit() or char in ".¥￥":
            token += char
            continue
        if char == "元" and any(ch.isdigit() for ch in token):
            requested_prices.append(f"{token}元")
        token = ""
    if not requested_prices:
        return None

    new_price = requested_prices[-1]
    for frame in frames:
        for field in ("description", "narration", "image_prompt", "subtitle_text", "text_overlay"):
            current = str(getattr(frame, field, "") or "")
            if "元" in current and any(ch.isdigit() for ch in current):
                return {
                    "action": "EDIT_FRAME",
                    "affected_frame_ids": [getattr(frame, "id", None)],
                    "modifications": {"price": new_price},
                    "needs_confirmation": False,
                    "assistant_content": (
                        f"好的，已为您将第{getattr(frame, 'sequence', '?')}个分镜中的价格修改为{new_price}，"
                        "相关旁白和画面文案会一起同步。"
                    ),
                    "confidence": 0.7,
                }
    return None


def _postprocess_project_plan(plan: dict, content: str, frames: list = None) -> dict:
    fallback_edit_plan = _fallback_project_edit_intent(content, frames)
    if not fallback_edit_plan:
        return plan

    modifications = plan.get("modifications", {}) or {}
    has_supported_modifications = any(key in SUPPORTED_EDIT_FIELDS for key in modifications)
    if plan.get("action") == "ASK_CLARIFYING":
        return fallback_edit_plan
    if plan.get("action") == "EDIT_FRAME" and not has_supported_modifications:
        return fallback_edit_plan
    return plan


def _fallback_project_intent(content: str, workflow_stage: str, frames: list = None) -> dict:
    """降级规则：LLM失败时使用硬编码规则"""
    text = (content or "").strip()
    if not text:
        return {"action": "CONVERSE", "affected_frame_ids": [], "modifications": {},
                "needs_confirmation": False, "assistant_content": "", "confidence": 0.5}

    edit_plan = _fallback_project_edit_intent(text, frames)
    if edit_plan:
        return edit_plan

    # 确认意图
    confirm_words = ("确认", "可以", "没问题", "下一步", "继续", "通过")
    if any(word in text for word in confirm_words):
        if workflow_stage == "script":
            return {"action": "CONFIRM_AND_ADVANCE", "affected_frame_ids": [], "modifications": {},
                    "needs_confirmation": False, "assistant_content": "已确认剧本，开始生成图片。",
                    "confidence": 0.9}
        elif workflow_stage == "image":
            return {"action": "CONFIRM_AND_ADVANCE", "affected_frame_ids": [], "modifications": {},
                    "needs_confirmation": False, "assistant_content": "已确认图片，开始生成视频。",
                    "confidence": 0.9}
        elif workflow_stage == "video":
            return {"action": "CONFIRM_AND_ADVANCE", "affected_frame_ids": [], "modifications": {},
                    "needs_confirmation": False, "assistant_content": "视频已确认完成。",
                    "confidence": 0.9}

    # 普通对话
    return {"action": "CONVERSE", "affected_frame_ids": [], "modifications": {},
            "needs_confirmation": False, "assistant_content": "", "confidence": 0.6}


# ============ 流式对话 ============

def stream_converse(
    content: str,
    workflow_stage: str = "created",
    stage_status: str = "idle",
    frame_count: int = 0,
    conversation_history: list = None,
):
    """
    项目内流式对话（非JSON输出）

    Args:
        content: 用户消息
        workflow_stage: 当前阶段
        stage_status: 阶段状态
        frame_count: 分镜数
        conversation_history: 对话历史
    """
    system_prompt = f"""你是「带货视频生成系统」的 AI 助手。你正在和用户讨论视频项目。

当前项目状态:
- 阶段: {workflow_stage}（{stage_status}）
- 共 {frame_count} 个分镜

你可以：
- 回答用户关于项目的问题
- 讨论创意方向和风格偏好
- 解释系统功能和操作方式
- 给出修改建议

用自然、友好的中文回复。不要输出 JSON 格式。"""

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        for msg in conversation_history[-10:]:
            role = msg.get("role", "user")
            msg_content = msg.get("content", "")
            if msg_content and role in ("user", "assistant"):
                messages.append({"role": role, "content": msg_content})
    messages.append({"role": "user", "content": content})

    try:
        llm = VolcanoLLM(key=None, model_name=None)
        request = ChatRequest(
            messages=[ChatMessage(**m) for m in messages],
            temperature=0.7,
            max_tokens=1000,
        )
        for chunk in llm.stream_chat(request):
            yield chunk
    except Exception as e:
        logger.error(f"Stream converse failed: {e}")
        yield "抱歉，对话服务暂时不可用，请稍后再试。"


def stream_entry_converse(content: str):
    """
    入口对话流式回复（无项目时）

    Args:
        content: 用户消息
    """
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

    try:
        llm = VolcanoLLM(key=None, model_name=None)
        request = ChatRequest(
            messages=[ChatMessage(**m) for m in messages],
            temperature=0.7,
            max_tokens=800,
        )
        for chunk in llm.stream_chat(request):
            yield chunk
    except Exception as e:
        logger.error(f"Stream entry converse failed: {e}")
        yield "抱歉，服务暂时不可用，请稍后再试。"


# ============ 意图识别服务单例 ============

class IntentService:
    """统一意图识别服务"""

    def classify_entry(self, content: str) -> dict:
        """入口对话意图识别"""
        return classify_entry_intent(content)

    def classify_project(
        self,
        content: str,
        workflow_stage: str = "created",
        stage_status: str = "idle",
        frames: list = None,
        conversation_history: list = None,
    ) -> dict:
        """项目内意图识别"""
        return classify_project_intent(
            content=content,
            workflow_stage=workflow_stage,
            stage_status=stage_status,
            frames=frames,
            conversation_history=conversation_history,
        )

    def stream_converse(
        self,
        content: str,
        workflow_stage: str = "created",
        stage_status: str = "idle",
        frame_count: int = 0,
        conversation_history: list = None,
    ):
        """项目内流式对话"""
        return stream_converse(
            content=content,
            workflow_stage=workflow_stage,
            stage_status=stage_status,
            frame_count=frame_count,
            conversation_history=conversation_history,
        )

    def stream_entry_converse(self, content: str):
        """入口对话流式回复"""
        return stream_entry_converse(content)


# 全局单例
intent_service = IntentService()
