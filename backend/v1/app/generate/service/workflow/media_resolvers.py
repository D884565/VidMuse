"""Shared media generation input resolvers for chat-editable frame fields."""
from __future__ import annotations


def _clean(value) -> str:
    return str(value or "").strip()


def resolve_image_generation_prompt(frame) -> str:
    base = _clean(getattr(frame, "image_prompt", None)) or _clean(getattr(frame, "description", None))
    ai_params = getattr(frame, "ai_params", None) or {}
    revision = _clean(ai_params.get("image_revision_instruction"))
    if revision:
        return f"{base}\nUser image revision: {revision}" if base else revision
    return base


def resolve_video_generation_prompt(frame) -> str:
    return (
        _clean(getattr(frame, "video_prompt", None))
        or _clean(getattr(frame, "prompt", None))
        or _clean(getattr(frame, "description", None))
    )


def resolve_tts_text(frame) -> str:
    ai_params = getattr(frame, "ai_params", None) or {}
    return (
        _clean(getattr(frame, "narration", None))
        or _clean(ai_params.get("text"))
        or _clean(getattr(frame, "description", None))
    )
