from types import SimpleNamespace

import asyncio

import backend.v1.app.assets.service.asset_service as asset_service_module
from backend.v1.app.assets.service.asset_analysis_orchestrator import AssetAnalysisOrchestrator
from backend.v1.app.assets.service.asset_service import AssetService


def test_image_asset_runs_product_analysis_only(monkeypatch):
    orchestrator = AssetAnalysisOrchestrator()
    asset = SimpleNamespace(id=1, type=1, url="https://cdn.test/image.png", content_text=None, duration=None)

    monkeypatch.setattr(orchestrator, "_run_product_analysis_for_asset", lambda current_asset: {
        "product_name": "eye massager",
        "selling_points": ["warming"],
        "audience": "office workers",
        "scenarios": ["office"],
        "visual_features": ["curved visor"],
        "keywords": ["eye care"],
        "raw": {"basic_info": {"product_name": "eye massager"}},
    })
    monkeypatch.setattr(orchestrator, "_run_video_strategy_analysis_for_asset", lambda current_asset: {
        "hook_strategy": ["should not be used"]
    })

    result = orchestrator.analyze_asset(asset)

    assert result["material_type"] == "image"
    assert result["video_insights"] == {}
    assert result["product_insights"]["product_name"] == "eye massager"


def test_video_asset_merges_video_and_product_analysis(monkeypatch):
    orchestrator = AssetAnalysisOrchestrator()
    asset = SimpleNamespace(id=2, type=2, url="https://cdn.test/demo.mp4", content_text=None, duration=12)

    monkeypatch.setattr(orchestrator, "_run_video_strategy_analysis_for_asset", lambda current_asset: {
        "hook_strategy": ["lead with pain point"],
        "rhythm_strategy": ["fast first three seconds"],
        "shot_strategy": ["high-frequency close-ups"],
        "conversion_strategy": ["proof before offer"],
        "raw": {"video_basic_info": {"product_name": "coffee cup"}},
    })
    monkeypatch.setattr(orchestrator, "_run_product_analysis_for_asset", lambda current_asset: {
        "product_name": "coffee cup",
        "selling_points": ["heat retention"],
        "audience": "commuters",
        "scenarios": ["commute"],
        "visual_features": ["matte body"],
        "keywords": ["thermos"],
        "raw": {"basic_info": {"product_name": "coffee cup"}},
    })

    result = orchestrator.analyze_asset(asset)

    assert result["video_insights"]["hook_strategy"] == ["lead with pain point"]
    assert result["product_insights"]["selling_points"] == ["heat retention"]
    assert "lead with pain point" in result["prompt_summary"]["strategy_points"]


def test_text_asset_uses_text_product_analysis(monkeypatch):
    orchestrator = AssetAnalysisOrchestrator()
    asset = SimpleNamespace(id=3, type=4, url="", content_text="Selling point: sensitive skin friendly", duration=None)

    monkeypatch.setattr(orchestrator, "_run_product_analysis_for_asset", lambda current_asset: {
        "product_name": "repair serum",
        "selling_points": ["sensitive skin friendly"],
        "audience": "sensitive skin users",
        "scenarios": ["night repair"],
        "visual_features": [],
        "keywords": ["repair"],
        "raw": {"basic_info": {"product_name": "repair serum"}},
    })

    result = orchestrator.analyze_asset(asset)

    assert result["material_type"] == "text"
    assert result["product_insights"]["audience"] == "sensitive skin users"


def test_partial_video_analysis_can_still_return_prompt_summary(monkeypatch):
    orchestrator = AssetAnalysisOrchestrator()
    asset = SimpleNamespace(id=4, type=2, url="https://cdn.test/fallback.mp4", content_text=None, duration=8)

    def fail_video(_asset):
        raise RuntimeError("video parse failed")

    monkeypatch.setattr(orchestrator, "_run_video_strategy_analysis_for_asset", fail_video)
    monkeypatch.setattr(orchestrator, "_run_product_analysis_for_asset", lambda current_asset: {
        "product_name": "massage gun",
        "selling_points": ["deep relief"],
        "audience": "fitness users",
        "scenarios": ["post workout"],
        "visual_features": ["gun-shaped body"],
        "keywords": ["recovery"],
        "raw": {},
    })

    result = orchestrator.analyze_asset(asset)

    assert result["product_insights"]["product_name"] == "massage gun"
    assert result["prompt_summary"]["selling_points"] == ["deep relief"]


def test_parse_asset_returns_merged_ai_features(monkeypatch):
    fake_asset = SimpleNamespace(
        id=9,
        type=1,
        title="test image",
        url="https://cdn.test/image.png",
        duration=None,
        ai_features=None,
        parsing_status="pending",
        execution_id=None,
        parsing_error=None,
    )

    def fake_update(_db, _asset_id, data):
        merged = {**fake_asset.__dict__, **data}
        return SimpleNamespace(**merged)

    monkeypatch.setattr(
        "backend.v1.app.assets.service.asset_service.AssetDAO.get_asset_by_id",
        lambda db, asset_id: fake_asset,
    )
    monkeypatch.setattr(
        "backend.v1.app.assets.service.asset_service.AssetDAO.update_asset",
        fake_update,
    )
    monkeypatch.setattr(
        asset_service_module.AssetService,
        "_analysis_orchestrator",
        SimpleNamespace(
            analyze_asset=lambda asset: {
                "analysis_version": 1,
                "material_type": "image",
                "video_insights": {},
                "product_insights": {"product_name": "test"},
                "prompt_summary": {
                    "strategy_points": [],
                    "selling_points": [],
                    "visual_points": [],
                    "audience": "",
                    "scenarios": [],
                    "keywords": [],
                    "reference_text": "",
                },
            }
        ),
    )

    result = asyncio.run(AssetService.parse_asset(db=object(), asset_id=9))

    assert result["analysis_completed"] is True
    assert result["ai_features"]["material_type"] == "image"
