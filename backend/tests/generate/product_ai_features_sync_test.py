"""
测试商品解析结果同步到 products.ai_features 字段

验证：
1. AssetPersistProcessor 在有 product_id 时会更新 products 表
2. products.ai_features 和 assets.ai_features 内容一致
3. 所有调用 parse_product 的地方都在 close 前 commit
"""
from pathlib import Path


def test_asset_persist_processor_commits_product_update():
    """AssetPersistProcessor 更新 product 后应显式 commit"""
    code = Path("backend/v1/app/pipeline/processors/common/asset_persist_processor.py").read_text(encoding="utf-8")

    # 找到更新 product 的代码段
    persist_section = code[code.index("def process"):]

    # 确认有 product_id 检查
    assert "product_id = context.get(\"product_id\")" in persist_section

    # 确认在 ProductDAO.update_product 之后有 db.commit()
    product_update_idx = persist_section.index("ProductDAO.update_product")
    after_update = persist_section[product_update_idx:]
    assert "db.commit()" in after_update, "ProductDAO.update_product 后应有 db.commit()"


def test_product_controller_commits_after_parse():
    """product_controller 中所有 parse_product 调用后都应 commit"""
    code = Path("backend/v1/app/product/controller/product_controller.py").read_text(encoding="utf-8")

    # 检查 create_product 中的后台任务
    create_section = code[code.index("def create_product"):code.index("def list_products")]
    assert "db_bg.commit()" in create_section, "create_product 后台任务应有 db_bg.commit()"

    # 检查手动触发解析
    parse_section = code[code.index("def parse_product"):code.index("def get_parse_status")]
    assert "db.commit()" in parse_section, "parse_product 端点应有 db.commit()"


def test_product_service_commits_after_parse_in_upload():
    """upload_and_create_product 中的后台任务应 commit"""
    code = Path("backend/v1/app/product/service/product_service.py").read_text(encoding="utf-8")

    upload_section = code[code.index("def upload_and_create_product"):]
    upload_section = upload_section[:upload_section.index("def list_products")]

    # 确认后台任务中有 commit
    assert "db_bg.commit()" in upload_section, "upload_and_create_product 后台任务应有 db_bg.commit()"


def test_asset_persist_processor_writes_same_data_to_both_tables():
    """AssetPersistProcessor 应将相同的 product_data 写入 assets 和 products"""
    code = Path("backend/v1/app/pipeline/processors/common/asset_persist_processor.py").read_text(encoding="utf-8")

    # 确认 asset 更新使用 product_data
    assert '"ai_features": product_data' in code

    # 确认 product 更新也使用 product_data
    persist_section = code[code.index("def process"):]
    product_section = persist_section[persist_section.index("product_id = context.get"):]
    assert '"ai_features": product_data' in product_section
