from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class MaterialResolver:
    """Resolve selected chat assets into usable prompt text and reference images."""

    @staticmethod
    def resolve_selected_assets(selected_assets: list[dict] | None, assets: Iterable[Any] | None) -> dict:
        asset_map = {
            int(getattr(asset, "id")): asset
            for asset in (assets or [])
            if getattr(asset, "id", None) is not None
        }

        selected_asset_ids: list[int] = []
        text_sections: list[str] = []
        reference_images: list[str] = []

        for index, item in enumerate(selected_assets or [], 1):
            try:
                asset_id = int(item.get("id"))
            except (TypeError, ValueError, AttributeError):
                continue

            asset = asset_map.get(asset_id)
            if not asset:
                continue

            selected_asset_ids.append(asset_id)
            asset_type = MaterialResolver._normalize_asset_type(item.get("type"), getattr(asset, "type", None))
            title = (item.get("title") or getattr(asset, "title", "") or f"素材 {asset_id}").strip()

            if asset_type == "text":
                content_text = (getattr(asset, "content_text", None) or "").strip()
                if content_text:
                    text_sections.append(f"素材 {index}（{title}）：\n{content_text}")
            elif asset_type == "image":
                image_url = (getattr(asset, "url", None) or "").strip()
                if image_url and image_url not in reference_images:
                    reference_images.append(image_url)

        text_reference = ""
        if text_sections:
            text_reference = "参考文本素材：\n" + "\n\n".join(text_sections)

        return {
            "selected_asset_ids": selected_asset_ids,
            "text_reference": text_reference,
            "reference_images": reference_images,
        }

    @staticmethod
    def _normalize_asset_type(raw_type: Any, fallback_type: Any) -> str:
        if isinstance(raw_type, str) and raw_type.strip():
            return raw_type.strip().lower()
        if fallback_type == 1:
            return "image"
        if fallback_type == 2:
            return "video"
        if fallback_type == 3:
            return "audio"
        if fallback_type == 4:
            return "text"
        return ""
