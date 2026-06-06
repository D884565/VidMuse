from __future__ import annotations


def _dedupe_list(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value).strip()
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result


def _build_reference_text(
    strategy_points: list[str],
    selling_points: list[str],
    visual_points: list[str],
    audience: str,
    scenarios: list[str],
    keywords: list[str],
) -> str:
    lines: list[str] = []
    if strategy_points:
        lines.append("Viral video strategy reference: " + "; ".join(strategy_points))
    if selling_points:
        lines.append("Product selling point reference: " + "; ".join(selling_points))
    if visual_points:
        lines.append("Visual feature reference: " + "; ".join(visual_points))
    if audience:
        lines.append(f"Audience: {audience}")
    if scenarios:
        lines.append("Scenarios: " + "; ".join(scenarios))
    if keywords:
        lines.append("Keywords: " + "; ".join(keywords))
    return "\n".join(lines)


def build_asset_ai_features(
    material_type: str,
    video_insights: dict | None = None,
    product_insights: dict | None = None,
) -> dict:
    video_insights = video_insights or {}
    product_insights = product_insights or {}

    strategy_points = _dedupe_list(
        list(video_insights.get("hook_strategy", []))
        + list(video_insights.get("rhythm_strategy", []))
        + list(video_insights.get("shot_strategy", []))
        + list(video_insights.get("conversion_strategy", []))
    )
    selling_points = _dedupe_list(product_insights.get("selling_points", []))
    visual_points = _dedupe_list(product_insights.get("visual_features", []))
    scenarios = _dedupe_list(product_insights.get("scenarios", []))
    keywords = _dedupe_list(product_insights.get("keywords", []))
    audience = str(product_insights.get("audience", "") or "").strip()

    return {
        "analysis_version": 1,
        "material_type": material_type,
        "video_insights": video_insights,
        "product_insights": product_insights,
        "prompt_summary": {
            "strategy_points": strategy_points,
            "selling_points": selling_points,
            "visual_points": visual_points,
            "audience": audience,
            "scenarios": scenarios,
            "keywords": keywords,
            "reference_text": _build_reference_text(
                strategy_points=strategy_points,
                selling_points=selling_points,
                visual_points=visual_points,
                audience=audience,
                scenarios=scenarios,
                keywords=keywords,
            ),
        },
    }
