from types import SimpleNamespace

from backend.v1.app.generate.service.chat.material_resolver import MaterialResolver


def test_resolver_extracts_text_body_and_image_urls_from_selected_assets():
    assets = [
        SimpleNamespace(id=11, type=4, title="卖点文案", url="", content_text="轻量机身\n续航长"),
        SimpleNamespace(id=12, type=1, title="产品主图", url="https://cdn.test/product-main.png", content_text=None),
        SimpleNamespace(id=13, type=4, title="空白文本", url="", content_text="   "),
    ]

    selected_assets = [
        {"id": 11, "type": "text", "title": "卖点文案"},
        {"id": 12, "type": "image", "title": "产品主图"},
        {"id": 13, "type": "text", "title": "空白文本"},
    ]

    result = MaterialResolver.resolve_selected_assets(selected_assets, assets)

    assert result["reference_images"] == ["https://cdn.test/product-main.png"]
    assert "素材 1（卖点文案）" in result["text_reference"]
    assert "轻量机身" in result["text_reference"]
    assert "续航长" in result["text_reference"]
    assert "空白文本" not in result["text_reference"]


def test_resolver_ignores_missing_assets_and_preserves_selected_order():
    assets = [
        SimpleNamespace(id=22, type=1, title="细节图", url="https://cdn.test/detail.png", content_text=None),
        SimpleNamespace(id=21, type=4, title="脚本参考", url="", content_text="先讲痛点，再讲解决方案"),
    ]

    selected_assets = [
        {"id": 21, "type": "text", "title": "脚本参考"},
        {"id": 99, "type": "image", "title": "不存在"},
        {"id": 22, "type": "image", "title": "细节图"},
    ]

    result = MaterialResolver.resolve_selected_assets(selected_assets, assets)

    assert result["reference_images"] == ["https://cdn.test/detail.png"]
    assert result["selected_asset_ids"] == [21, 22]
    assert result["text_reference"].startswith("参考文本素材")


def test_resolver_treats_text_and_image_as_only_generation_inputs():
    assets = [
        SimpleNamespace(id=31, type=2, title="视频参考", url="https://cdn.test/demo.mp4", content_text=None),
        SimpleNamespace(id=32, type=3, title="音频参考", url="https://cdn.test/demo.mp3", content_text=None),
    ]

    selected_assets = [
        {"id": 31, "type": "video", "title": "视频参考"},
        {"id": 32, "type": "audio", "title": "音频参考"},
    ]

    result = MaterialResolver.resolve_selected_assets(selected_assets, assets)

    assert result["reference_images"] == []
    assert result["text_reference"] == ""
    assert result["selected_asset_ids"] == [31, 32]
