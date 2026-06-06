from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class MaterialResolver:
    """Resolve selected chat assets into parsed material prompt text."""

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
            prompt_summary = ai_features.get("prompt_summary", {}) if isinstance(ai_features, dict) else {}
            reference_text = str(prompt_summary.get("reference_text", "") or "").strip()
            if reference_text:
                prompt_chunks.append(reference_text)

        return {
            "selected_asset_ids": selected_asset_ids,
            "material_prompt_text": "\n\n".join(prompt_chunks),
        }
