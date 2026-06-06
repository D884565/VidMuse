from __future__ import annotations


def _join_unique(values: list[str]) -> str:
    return "; ".join(dict.fromkeys([str(value).strip() for value in values if str(value).strip()]))


def format_material_prompt_section(materials: list[dict]) -> str:
    if not materials:
        return ""

    strategy_points: list[str] = []
    selling_points: list[str] = []
    visual_points: list[str] = []
    audiences: list[str] = []
    scenarios: list[str] = []
    keywords: list[str] = []

    for item in materials:
        summary = item.get("prompt_summary", {}) or {}
        strategy_points.extend(summary.get("strategy_points", []) or [])
        selling_points.extend(summary.get("selling_points", []) or [])
        visual_points.extend(summary.get("visual_points", []) or [])
        if summary.get("audience"):
            audiences.append(summary["audience"])
        scenarios.extend(summary.get("scenarios", []) or [])
        keywords.extend(summary.get("keywords", []) or [])

    lines = ["## Material analysis reference"]
    if strategy_points:
        lines.append("Viral video strategy reference: " + _join_unique(strategy_points))
    if selling_points or visual_points or audiences or scenarios or keywords:
        lines.append("Product feature reference:")
        if selling_points:
            lines.append("Core selling points: " + _join_unique(selling_points))
        if visual_points:
            lines.append("Visual focus: " + _join_unique(visual_points))
        if audiences:
            lines.append("Audience: " + _join_unique(audiences))
        if scenarios:
            lines.append("Scenarios: " + _join_unique(scenarios))
        if keywords:
            lines.append("Keywords: " + _join_unique(keywords))
    lines.append("Absorb these strategies and selling points, but do not directly copy the source wording.")
    return "\n".join(lines)
