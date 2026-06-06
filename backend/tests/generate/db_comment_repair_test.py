from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "repair_db_comments.py"


def load_module():
    spec = spec_from_file_location("repair_db_comments", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_init_sql_comments_uses_readable_chinese_source_of_truth():
    module = load_module()
    sql_text = (ROOT / "resources" / "init.sql").read_text(encoding="utf-8")

    comments = module.parse_init_sql_comments(sql_text)

    assert comments["assets"]["table_comment"] == "素材库"
    assert comments["assets"]["columns"]["title"] == "资产标题"
    assert comments["project_assets"]["table_comment"] == "项目素材绑定表"
    assert comments["generation_task_steps"]["columns"]["step_name"] == "步骤名称"


def test_build_comment_fix_sql_generates_alter_statements_from_show_create_table():
    module = load_module()
    desired = {
        "table_comment": "素材库",
        "columns": {
            "title": "资产标题",
            "url": "存储URL",
        },
    }
    show_create_table = """CREATE TABLE `assets` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(200) DEFAULT NULL COMMENT '璧勪骇鏍囬',
  `url` varchar(500) NOT NULL COMMENT '瀛樺偍URL',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='绱犳潗搴'"""

    statements = module.build_comment_fix_sql("assets", show_create_table, desired)

    assert "ALTER TABLE `assets` MODIFY COLUMN `title` varchar(200) DEFAULT NULL COMMENT '资产标题';" in statements
    assert "ALTER TABLE `assets` MODIFY COLUMN `url` varchar(500) NOT NULL COMMENT '存储URL';" in statements
    assert "ALTER TABLE `assets` COMMENT = '素材库';" in statements
