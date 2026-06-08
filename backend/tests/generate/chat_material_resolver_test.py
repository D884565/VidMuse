from types import SimpleNamespace

from backend.v1.app.generate.service.chat.material_resolver import MaterialResolver


def test_resolver_collects_selected_asset_ids_and_parsed_prompt_text():
    assets = [
        SimpleNamespace(
            id=11,
            type=4,
            title="selling copy",
            ai_features={"prompt_summary": {"reference_text": "Product selling point reference: lightweight; long battery life"}},
        ),
        SimpleNamespace(
            id=12,
            type=1,
            title="hero image",
            ai_features={"prompt_summary": {"reference_text": "Visual feature reference: metallic frame"}},
        ),
        SimpleNamespace(id=13, type=4, title="blank text", ai_features={}),
    ]

    selected_assets = [
        {"id": 11, "type": "text", "title": "selling copy"},
        {"id": 12, "type": "image", "title": "hero image"},
        {"id": 13, "type": "text", "title": "blank text"},
    ]

    result = MaterialResolver.resolve_selected_assets(selected_assets, assets)

    assert result["selected_asset_ids"] == [11, 12, 13]
    assert "lightweight" in result["material_prompt_text"]
    assert "metallic frame" in result["material_prompt_text"]
    assert "reference_images" not in result
    assert "text_reference" not in result


def test_resolver_ignores_missing_assets_and_preserves_selected_order():
    assets = [
        SimpleNamespace(
            id=22,
            type=1,
            title="detail image",
            ai_features={"prompt_summary": {"reference_text": "Visual feature reference: matte material"}},
        ),
        SimpleNamespace(
            id=21,
            type=4,
            title="script note",
            ai_features={"prompt_summary": {"reference_text": "Product selling point reference: pain point first, solution second"}},
        ),
    ]

    selected_assets = [
        {"id": 21, "type": "text", "title": "script note"},
        {"id": 99, "type": "image", "title": "missing"},
        {"id": 22, "type": "image", "title": "detail image"},
    ]

    result = MaterialResolver.resolve_selected_assets(selected_assets, assets)

    assert result["selected_asset_ids"] == [21, 22]
    assert result["material_prompt_text"].startswith("Product selling point reference")


def test_resolver_skips_assets_without_parsed_material_prompt_text():
    assets = [
        SimpleNamespace(id=31, type=2, title="video ref", ai_features={}),
        SimpleNamespace(id=32, type=3, title="audio ref", ai_features={}),
    ]

    selected_assets = [
        {"id": 31, "type": "video", "title": "video ref"},
        {"id": 32, "type": "audio", "title": "audio ref"},
    ]

    result = MaterialResolver.resolve_selected_assets(selected_assets, assets)

    assert result["material_prompt_text"] == ""
    assert result["selected_asset_ids"] == [31, 32]


def test_resolver_reads_nested_product_data_format():
    assets = [
        SimpleNamespace(
            id=41,
            title="product analysis",
            ai_features={
                "product_data": {
                    "basic_info": {
                        "product_name": "Foldable Desk Lamp",
                        "description": "portable eye-care lamp",
                        "target_audience": "students",
                        "scenarios": ["dorm", "office"],
                    },
                    "selling_points": ["long battery", "soft light"],
                    "tags": ["portable"],
                    "keywords": ["study lamp"],
                }
            },
        )
    ]

    result = MaterialResolver.resolve_selected_assets([{"id": 41}], assets)

    assert result["selected_asset_ids"] == [41]
    assert "Foldable Desk Lamp" in result["material_prompt_text"]
    assert "long battery" in result["material_prompt_text"]
    assert "study lamp" in result["material_prompt_text"]


def test_resolver_reads_structured_prompt_summary_without_reference_text():
    assets = [
        SimpleNamespace(
            id=42,
            title="structured summary",
            ai_features={
                "prompt_summary": {
                    "selling_points": ["fast warm-up"],
                    "visual_points": ["steam close-up"],
                    "audience": "busy parents",
                    "scenarios": ["morning breakfast"],
                }
            },
        )
    ]

    result = MaterialResolver.resolve_selected_assets([{"id": 42}], assets)

    assert "fast warm-up" in result["material_prompt_text"]
    assert "steam close-up" in result["material_prompt_text"]
    assert "busy parents" in result["material_prompt_text"]
