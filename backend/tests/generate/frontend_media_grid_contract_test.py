from pathlib import Path


def test_media_grid_supports_text_material_and_reupload_actions():
    source = Path("frontend/src/components/Media/MediaGrid.jsx").read_text(encoding="utf-8")

    assert "createTextAsset" in source
    assert "updateTextAsset" in source
    assert "reuploadImageAsset" in source
    assert "content_text" in source
    assert "text" in source.lower()


def test_media_grid_uses_material_library_action_copy():
    grid_source = Path("frontend/src/components/Media/MediaGrid.jsx").read_text(encoding="utf-8")
    card_source = Path("frontend/src/components/Media/MediaCard.jsx").read_text(encoding="utf-8")
    dialog_source = Path("frontend/src/components/Common/ConfirmDialog.jsx").read_text(encoding="utf-8")

    assert "新增素材" in grid_source
    assert "新建文本" in grid_source
    assert "上传图片" in grid_source
    assert "['all', 'image', 'text']" in grid_source
    assert "删除素材" in grid_source
    assert "重新上传图片素材" in card_source
    assert "取消" in dialog_source
    assert "删除" in dialog_source


def test_media_card_prefers_full_image_preview_over_cover_crop():
    source = Path("frontend/src/components/Media/MediaCard.jsx").read_text(encoding="utf-8")

    assert "object-contain" in source
    assert "object-cover" not in source
