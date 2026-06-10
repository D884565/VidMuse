from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class MaterialResolver:
    """Resolve selected chat assets into parsed material prompt text."""

    @staticmethod
    def _build_reference_text(ai_features: dict) -> str:
        """从 ai_features 中提取可读的参考文本，兼容 product_data 格式和旧 prompt_summary 格式。"""
        if not isinstance(ai_features, dict):
            return ""

        def append_value(parts: list[str], label: str, value) -> None:
            if not value:
                return
            if isinstance(value, (list, tuple, set)):
                cleaned = [str(item).strip() for item in value if str(item).strip()]
                if cleaned:
                    parts.append(f"{label}: {', '.join(cleaned)}")
                return
            text = str(value).strip()
            if text:
                parts.append(f"{label}: {text}")

        # 优先读旧格式 prompt_summary.reference_text
        prompt_summary = ai_features.get("prompt_summary", {})
        if isinstance(prompt_summary, dict):
            ref = str(prompt_summary.get("reference_text", "") or "").strip()
            if ref:
                return ref

            parts = []
            append_value(parts, "策略要点", prompt_summary.get("strategy_points"))
            append_value(parts, "核心卖点", prompt_summary.get("selling_points"))
            append_value(parts, "视觉要点", prompt_summary.get("visual_points"))
            append_value(parts, "目标人群", prompt_summary.get("audience"))
            append_value(parts, "使用场景", prompt_summary.get("scenarios"))
            if parts:
                return "\n".join(parts)

        # 从 product_data 格式或旧顶层格式构建
        product_data = ai_features.get("product_data", {})
        if not isinstance(product_data, dict):
            product_data = {}
        source = product_data or ai_features
        parts = []
        basic = source.get("basic_info", {})
        if isinstance(basic, dict):
            append_value(parts, "商品", basic.get("product_name") or basic.get("name"))
            append_value(parts, "介绍", basic.get("description"))
            append_value(parts, "目标人群", basic.get("target_audience"))
            append_value(parts, "使用场景", basic.get("scenarios"))

        append_value(parts, "核心卖点", source.get("selling_points"))
        append_value(parts, "标签", source.get("tags"))
        append_value(parts, "关键词", source.get("keywords"))

        return "\n".join(parts)

    @staticmethod
    def resolve_selected_assets(selected_assets: list[dict] | None, assets: Iterable[Any] | None) -> dict:
        asset_map = {
            int(getattr(asset, "id")): asset
            for asset in (assets or [])
            if getattr(asset, "id", None) is not None
        }

        selected_asset_ids: list[int] = []
        prompt_chunks: list[str] = []

        for item in selected_assets or []:
            try:
                asset_id = int(item.get("id"))
            except (TypeError, ValueError, AttributeError):
                continue

            asset = asset_map.get(asset_id)
            if not asset:
                continue

            selected_asset_ids.append(asset_id)
            ai_features = getattr(asset, "ai_features", None) or {}
            reference_text = MaterialResolver._build_reference_text(ai_features)
            if reference_text:
                prompt_chunks.append(reference_text)

        return {
            "selected_asset_ids": selected_asset_ids,
            "material_prompt_text": "\n\n".join(prompt_chunks),
        }
