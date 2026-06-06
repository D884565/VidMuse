"""将 backend/seed/bgm/ 下的音频文件导入 BGM 库（本地模式，不上传对象存储）。

用法:
    python scripts/seed_bgm.py                  # 导入默认目录 backend/seed/bgm/
    python scripts/seed_bgm.py /path/to/bgm     # 导入指定目录
"""
import sys
import os

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.store.database.sync_database import SessionLocal
# 确保所有模型被导入，SQLAlchemy relationship 能正确解析
import backend.v1.app.models  # noqa
from backend.v1.app.assets.service.bgm_import import import_bgm_folder


def main():
    default_dir = os.path.join(PROJECT_ROOT, "backend", "seed", "bgm")
    root_dir = sys.argv[1] if len(sys.argv) > 1 else default_dir

    if not os.path.isdir(root_dir):
        print(f"目录不存在: {root_dir}")
        print("请在 backend/seed/bgm/ 下放置音频文件，目录结构示例:")
        print("  backend/seed/bgm/轻松/track1.mp3")
        print("  backend/seed/bgm/电子/track2.mp3")
        sys.exit(1)

    db = SessionLocal()
    try:
        result = import_bgm_folder(db, root_dir, local=True)
        db.commit()
        print(f"导入完成: {result['imported']} 首, 跳过 {result['skipped']} 首")
        if result["errors"]:
            print("错误:")
            for e in result["errors"]:
                print(f"  - {e}")
    except Exception as e:
        db.rollback()
        print(f"导入失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
