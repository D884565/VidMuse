from pathlib import Path


def test_backend_bootstrap_ensures_product_assets_table_on_startup():
    schema_source = Path("backend/store/database/schema_bootstrap.py").read_text(encoding="utf-8")
    main_source = Path("backend/v1/main.py").read_text(encoding="utf-8")

    assert "ProductAsset.__table__" in schema_source
    assert "Base.metadata.create_all" in schema_source
    assert "ensure_product_assets_table()" in main_source
