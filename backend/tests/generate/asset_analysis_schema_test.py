from backend.v1.app.assets.service.asset_analysis_schema import build_asset_ai_features


def test_build_asset_ai_features_merges_video_and_product_namespaces():
    result = build_asset_ai_features(
        material_type="video",
        video_insights={
            "hook_strategy": ["3-second pain-point hook"],
            "rhythm_strategy": ["fast first half"],
            "shot_strategy": ["tight product close-ups"],
            "conversion_strategy": ["show promo after proof"],
            "raw": {"video_basic_info": {"product_name": "portable blender cup"}},
        },
        product_insights={
            "product_name": "portable blender cup",
            "selling_points": ["lightweight", "long battery life"],
            "audience": "office commuters",
            "scenarios": ["office", "gym"],
            "visual_features": ["transparent cup body", "carry handle"],
            "keywords": ["fresh blend", "portable"],
            "raw": {"basic_info": {"product_name": "portable blender cup"}},
        },
    )

    assert result["analysis_version"] == 1
    assert result["material_type"] == "video"
    assert result["video_insights"]["hook_strategy"] == ["3-second pain-point hook"]
    assert result["product_insights"]["selling_points"] == ["lightweight", "long battery life"]
    assert "3-second pain-point hook" in result["prompt_summary"]["strategy_points"]
    assert "lightweight" in result["prompt_summary"]["selling_points"]
    assert result["prompt_summary"]["audience"] == "office commuters"


def test_build_asset_ai_features_handles_image_without_video_namespace():
    result = build_asset_ai_features(
        material_type="image",
        video_insights=None,
        product_insights={
            "product_name": "sun spray",
            "selling_points": ["fast dry-down"],
            "audience": "outdoor users",
            "scenarios": ["beach"],
            "visual_features": ["gradient bottle"],
            "keywords": ["lightweight finish"],
            "raw": {"basic_info": {"product_name": "sun spray"}},
        },
    )

    assert result["material_type"] == "image"
    assert result["video_insights"] == {}
    assert result["product_insights"]["product_name"] == "sun spray"
    assert result["prompt_summary"]["visual_points"] == ["gradient bottle"]


def test_build_asset_ai_features_builds_reference_text_without_dumping_raw_json():
    result = build_asset_ai_features(
        material_type="text",
        video_insights=None,
        product_insights={
            "product_name": "hand cream",
            "selling_points": ["non-greasy", "long-lasting fragrance"],
            "audience": "dry skin users",
            "scenarios": ["office"],
            "visual_features": [],
            "keywords": ["moisturizing"],
            "raw": {"debug": "only for storage"},
        },
    )

    reference_text = result["prompt_summary"]["reference_text"]
    assert "non-greasy" in reference_text
    assert "long-lasting fragrance" in reference_text
    assert "debug" not in reference_text
