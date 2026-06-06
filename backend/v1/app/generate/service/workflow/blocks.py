"""工作流对话消息块构建器。

这些 helper 只负责把后端产物整理成前端可渲染的结构化 blocks。
业务执行仍然放在 workflow/image/video service 中，避免消息渲染逻辑和任务调度耦合。
"""
from __future__ import annotations

from typing import Iterable


def _duration_value(value) -> float:
    """安全地将时长值转为 float，失败时返回 0.0。"""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_script_stage_blocks(frames: Iterable) -> list[dict]:
    """构建剧本阶段的结构化 blocks：摘要卡片 + 分镜表格 + 对话式追问。"""
    frames = list(frames)
    total_duration = sum(_duration_value(getattr(frame, "duration", 0)) for frame in frames)
    summary = {
        "type": "script_summary",
        "title": "剧本方案已生成",
        "theme": "围绕商品卖点生成短视频分镜脚本",
        "style": "可在对话中继续指定风格、节奏和画面方向",
        "visual_plan": "每个分镜包含画面描述、旁白、图片提示词和视频提示词",
        "frame_count": len(frames),
        "total_duration": round(total_duration, 1),
    }
    table = {
        "type": "storyboard_table",
        "frames": [
            {
                "id": getattr(frame, "id", None),
                "sequence": getattr(frame, "sequence", None),
                "duration": _duration_value(getattr(frame, "duration", 0)),
                "scene": getattr(frame, "description", None) or "",
                "narration": getattr(frame, "narration", None) or "",
                "image_prompt": getattr(frame, "image_prompt", None) or getattr(frame, "description", None) or "",
                "video_prompt": getattr(frame, "video_prompt", None) or getattr(frame, "prompt", None) or "",
            }
            for frame in frames
        ],
    }
    follow_up = {
        "type": "follow_up",
        "message": "剧本和分镜方案已经准备好了。你看一下节奏、卖点和画面方向，如果没问题，回复「继续」或「可以生成图片」，我就开始生成首帧图片；如果要改，直接告诉我想调整哪一段。",
    }
    return [summary, table, follow_up]


def build_image_stage_blocks(frames: Iterable) -> list[dict]:
    """构建图片阶段的结构化 blocks：图片网格 + 对话式追问。"""
    frames = list(frames)
    return [
        {
            "type": "image_grid",
            "images": [
                {
                    "frame_id": getattr(frame, "id", None),
                    "sequence": getattr(frame, "sequence", None),
                    "url": getattr(frame, "image_url", None),
                    "status": getattr(frame, "status", None),
                    "description": getattr(frame, "description", None) or "",
                    "error_message": getattr(frame, "error_message", None),
                }
                for frame in frames
            ],
        },
        {
            "type": "follow_up",
            "message": "首帧图片已经生成好了。你看一下商品质感、构图和每个镜头的画面方向；如果没问题，回复「继续」或「可以生成视频」，我就开始批量生成视频。若某张图不满意，直接说例如「图 3 换成更自然的状态」。",
        },
    ]


def build_video_stage_blocks(project, *, video_url: str | None = None, task_id: int | None = None) -> list[dict]:
    """构建视频阶段的结构化 blocks：视频播放卡片 + 对话式追问。"""
    url = video_url or getattr(project, "video_output_url", None)
    return [
        {
            "type": "video_card",
            "video_url": url,
            "audio_url": getattr(project, "audio_url", None),
            "task_id": task_id or getattr(project, "last_task_id", None),
            "status": getattr(project, "stage_status", None),
        },
        {
            "type": "follow_up",
            "message": "视频阶段已经推进完成。你可以先预览成片；如果满意，回复「确认完成」。如果还想改配音、某个镜头或首帧，直接告诉我具体位置和修改方向。",
        },
    ]


def build_frame_editor_block(frame) -> dict:
    """构建分镜编辑 block，用于在对话中 inline 编辑分镜字段。"""
    return {
        "type": "frame_editor",
        "frame_id": getattr(frame, "id", None),
        "sequence": getattr(frame, "sequence", None),
        "fields": {
            "description": {
                "value": getattr(frame, "description", None) or "",
                "editable": True,
            },
            "narration": {
                "value": getattr(frame, "narration", None) or "",
                "editable": True,
            },
            "image_prompt": {
                "value": getattr(frame, "image_prompt", None) or "",
                "editable": True,
            },
            "video_prompt": {
                "value": getattr(frame, "video_prompt", None) or getattr(frame, "prompt", None) or "",
                "editable": True,
            },
            "duration": {
                "value": _duration_value(getattr(frame, "duration", 0)),
                "editable": True,
            },
        },
        "actions": [
            {"label": "保存修改", "action": "save"},
            {"label": "重新生成图片", "action": "regenerate_image"},
            {"label": "重新生成视频", "action": "regenerate_video"},
        ],
    }


def build_confirmation_preview_block(
    action: str,
    message: str,
    target_frames: list[int] | None = None,
    modifications: dict | None = None,
    pending_action_id: str | None = None,
) -> dict:
    """构建确认预览 block，用于 needs_confirmation=true 时展示待执行操作。"""
    return {
        "type": "confirmation_preview",
        "pending_action_id": pending_action_id,
        "pending_action": action,
        "message": message,
        "target_frames": target_frames or [],
        "modifications": modifications or {},
        "actions": [
            {"label": "确认执行", "action": "confirm_pending"},
            {"label": "取消", "action": "cancel_pending"},
        ],
    }


def build_progress_block(stage: str, status: str, task_id: int | None = None, message: str | None = None) -> dict:
    """构建进度卡片 block，用于显示当前任务的阶段、状态和提示信息。"""
    return {
        "type": "progress_card",
        "stage": stage,
        "status": status,
        "task_id": task_id,
        "message": message or "任务已开始，正在为你推进当前阶段。",
    }
