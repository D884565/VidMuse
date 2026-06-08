"""Shared media generation input resolvers for chat-editable frame fields."""
from __future__ import annotations

STYLE_PROMPT_MAP: dict[str, str] = {
    "cinematic": "cinematic lighting, film grain, dramatic shadows, shallow depth of field, movie still",
    "product": "clean studio lighting, product showcase, professional product photography, white background",
    "anime": "anime style, cel shading, vibrant colors, Japanese animation, illustrated",
    "realistic": "photorealistic, natural lighting, high detail, realistic textures, 8k photography",
    "lifestyle": "lifestyle photography, warm tones, natural setting, candid feel",
    "fashion": "fashion photography, editorial style, dramatic lighting, high contrast",
    "tech": "tech aesthetic, futuristic, neon accents, dark background, sleek design",
    "food": "food photography, appetizing, warm lighting, close-up, macro detail",
}


def get_style_prompt(style: str | None) -> str:
    """将项目风格映射为英文提示词片段。未知风格原样返回。"""
    if not style:
        return ""
    return STYLE_PROMPT_MAP.get(style.lower().strip(), style)


def _clean(value) -> str:
    return str(value or "").strip()


def resolve_image_generation_prompt(frame, style: str | None = None) -> str:
    base = _clean(getattr(frame, "image_prompt", None)) or _clean(getattr(frame, "description", None))
    ai_params = getattr(frame, "ai_params", None) or {}
    revision = _clean(ai_params.get("image_revision_instruction"))
    if revision:
        base = f"{base}\nUser image revision: {revision}" if base else revision
    price_target = _clean(ai_params.get("price_revision_target"))
    if price_target:
        originals = ai_params.get("price_revision_original")
        if isinstance(originals, str):
            original_tokens = [originals]
        elif isinstance(originals, list):
            original_tokens = [_clean(item) for item in originals if _clean(item)]
        else:
            original_tokens = []
        base = (
            f"{base}\nMUST render the visible price text as {price_target}."
            if base else f"MUST render the visible price text as {price_target}."
        )
        if original_tokens:
            forbidden = ", ".join(dict.fromkeys(original_tokens))
            base = f"{base}\nDo not render {forbidden} anywhere in the image."
    style_hint = get_style_prompt(style)
    if style_hint:
        base = f"{base}\nStyle: {style_hint}" if base else f"Style: {style_hint}"
    return base


def resolve_video_generation_prompt(frame, style: str | None = None) -> str:
    base = (
        _clean(getattr(frame, "video_prompt", None))
        or _clean(getattr(frame, "prompt", None))
        or _clean(getattr(frame, "description", None))
    )
    style_hint = get_style_prompt(style)
    if style_hint:
        base = f"{base}\nStyle: {style_hint}" if base else f"Style: {style_hint}"
    return base


def resolve_tts_text(frame) -> str:
    ai_params = getattr(frame, "ai_params", None) or {}
    return (
        _clean(getattr(frame, "narration", None))
        or _clean(ai_params.get("text"))
        or _clean(getattr(frame, "description", None))
    )
