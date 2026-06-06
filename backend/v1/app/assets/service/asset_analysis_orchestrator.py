from __future__ import annotations

from backend.v1.app.assets.service.asset_analysis_schema import build_asset_ai_features
from backend.v1.app.pipeline import ProductParsingPipeline, VideoParsingPipeline


class AssetAnalysisOrchestrator:
    def analyze_asset(self, asset) -> dict:
        material_type = self._material_type_name(getattr(asset, "type", None))
        video_insights: dict = {}
        product_insights: dict = {}

        if material_type == "video":
            try:
                video_insights = self._run_video_strategy_analysis_for_asset(asset) or {}
            except Exception:
                video_insights = {}
            try:
                product_insights = self._run_product_analysis_for_asset(asset) or {}
            except Exception:
                product_insights = {}
        elif material_type in {"image", "text"}:
            product_insights = self._run_product_analysis_for_asset(asset) or {}
        else:
            raise ValueError(f"unsupported asset type: {getattr(asset, 'type', None)}")

        if not video_insights and not product_insights:
            raise ValueError("no analysis result available")

        return build_asset_ai_features(
            material_type=material_type,
            video_insights=video_insights,
            product_insights=product_insights,
        )

    @staticmethod
    def _material_type_name(asset_type: int | None) -> str:
        return {1: "image", 2: "video", 4: "text"}.get(asset_type, "")

    def _run_product_analysis_for_asset(self, asset) -> dict:
        pipeline = ProductParsingPipeline(enable_persistence=False, persist_to_asset=False)
        input_data = {"asset_id": getattr(asset, "id", None)}
        asset_type = getattr(asset, "type", None)
        if asset_type == 1:
            input_data["images"] = [getattr(asset, "url", "")]
        elif asset_type == 4:
            input_data["description"] = getattr(asset, "content_text", "") or ""
        elif asset_type == 2:
            input_data["video_url"] = getattr(asset, "url", "")
            input_data["video_duration"] = getattr(asset, "duration", 0) or 0
        result = pipeline.run(input_data)
        if not result.get("success"):
            errors = result.get("errors") or ["product analysis failed"]
            raise ValueError(errors[0])
        product_data = result.get("data", {}).get("product_data", {}) or {}
        basic_info = product_data.get("basic_info", {}) or {}
        raw_tags = product_data.get("tags", []) or []
        visual_features = raw_tags if isinstance(raw_tags, list) else [raw_tags]
        return {
            "product_name": basic_info.get("product_name", ""),
            "selling_points": product_data.get("selling_points", []) or [],
            "audience": basic_info.get("target_audience", ""),
            "scenarios": basic_info.get("scenarios", []) or [],
            "visual_features": visual_features,
            "keywords": product_data.get("keywords", []) or [],
            "raw": product_data,
        }

    def _run_video_strategy_analysis_for_asset(self, asset) -> dict:
        pipeline = VideoParsingPipeline(enable_persistence=False, enable_vectorization=False)
        result = pipeline.run(
            {
                "video_id": getattr(asset, "id", None),
                "video_url": getattr(asset, "url", ""),
                "video_duration": getattr(asset, "duration", 0) or 0,
            }
        )
        if not result.get("success"):
            errors = result.get("errors") or ["video analysis failed"]
            raise ValueError(errors[0])

        ai_features = result.get("data", {}).get("ai_features", {}) or {}
        video_basic = ai_features.get("视频基本信息", {}) or {}

        def pick_first(*keys: str) -> list[str]:
            values: list[str] = []
            for key in keys:
                value = video_basic.get(key)
                if isinstance(value, list):
                    values.extend([str(item).strip() for item in value if str(item).strip()])
                elif value is not None and str(value).strip():
                    values.append(str(value).strip())
            return values

        return {
            "hook_strategy": pick_first("开头策略", "吸睛点", "钩子"),
            "rhythm_strategy": pick_first("节奏策略", "节奏"),
            "shot_strategy": pick_first("镜头策略", "画面表现", "镜头语言"),
            "conversion_strategy": pick_first("转化策略", "转化设计", "卖点结构"),
            "raw": ai_features,
        }
