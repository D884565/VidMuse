from pathlib import Path


def test_product_daos_do_not_commit_inside_service_transactions():
    product_dao = Path("backend/v1/app/product/dao/product_dao.py").read_text(encoding="utf-8")
    product_asset_dao = Path("backend/v1/app/product/dao/product_asset_dao.py").read_text(encoding="utf-8")

    forbidden_sections = [
        product_dao[product_dao.index("def create_product"):product_dao.index("def get_product_by_id")],
        product_dao[product_dao.index("def update_product"):product_dao.index("def delete_product")],
        product_dao[product_dao.index("def delete_product"):product_dao.index("def list_products")],
        product_asset_dao[product_asset_dao.index("def create_product_asset"):product_asset_dao.index("def create_product_assets_batch")],
        product_asset_dao[product_asset_dao.index("def create_product_assets_batch"):product_asset_dao.index("def get_assets_by_product_id")],
        product_asset_dao[product_asset_dao.index("def delete_product_asset"):product_asset_dao.index("def delete_all_by_product_id")],
        product_asset_dao[product_asset_dao.index("def delete_all_by_product_id"):],
    ]

    for section in forbidden_sections:
        assert "db.commit()" not in section
        assert "db.flush()" in section or ".delete()" in section

def test_product_service_commits_after_nested_write_transactions():
    service = Path("backend/v1/app/product/service/product_service.py").read_text(encoding="utf-8")

    create_section = service[service.index("def create_product"):service.index("def get_product")]
    update_section = service[service.index("def update_product"):service.index("def delete_product")]
    delete_section = service[service.index("def delete_product"):service.index("def parse_product")]

    for section in (create_section, update_section, delete_section):
        after_nested = section[section.index("with db.begin_nested():"):]
        assert "db.commit()" in after_nested

