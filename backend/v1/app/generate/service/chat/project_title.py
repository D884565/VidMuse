from __future__ import annotations

import re


def build_video_project_title(prompt: str | None, fallback: str = "未命名视频项目") -> str:
    """Build a concise project title from a conversational creation request."""
    text = _clean_text(prompt)
    if not text:
        return fallback

    product = _extract_product_phrase(text)
    if not product:
        return fallback
    if product.endswith("带货视频"):
        return product
    return f"{product}带货视频"


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def _extract_product_phrase(text: str) -> str:
    product = re.sub(r"https?://\S+", "", text)
    product = re.sub(r"[，。！？、；：,.!?;:\"'“”‘’（）()【】\[\]{}<>《》]", "", product)
    product = re.sub(r"^(请|麻烦|帮我|帮忙|我要|我想|想要|给我)?(生成|制作|创建|做|来)(一个|一条|一段|个|条|段)?", "", product)
    product = re.sub(r"(带货)?(短视频|视频|广告片|广告|推广片|推广|宣传片|宣传|种草)$", "", product)
    product = re.sub(r"(剧本|脚本|分镜)$", "", product)
    product = product.strip()
    return product[:24]
