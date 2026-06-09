from pathlib import Path


def test_asset_delete_unlinks_product_associations_before_deleting_asset():
    product_asset_dao = Path("backend/v1/app/product/dao/product_asset_dao.py").read_text(encoding="utf-8")
    asset_service = Path("backend/v1/app/assets/service/asset_service.py").read_text(encoding="utf-8")

    assert "def delete_all_by_asset_id" in product_asset_dao

    delete_section = asset_service[asset_service.index("def delete_asset"):asset_service.index("def get_path_after_baseurl")]
    unlink_index = delete_section.index("ProductAssetDAO.delete_all_by_asset_id")
    delete_index = delete_section.index("AssetDAO.delete_asset")

    assert unlink_index < delete_index
