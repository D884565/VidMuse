# -*- coding: utf-8 -*-
"""
BGM迁移脚本：将本地BGM上传到TOS，并更新数据库URL

使用方式:
    python -m backend.v1.app.assets.service.bgm_migrate_to_tos
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import uuid
import logging
from pathlib import Path

from sqlalchemy import text

from backend.store import get_storage_client
from backend.store.database.sync_database import SessionLocal

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# BGM本地目录 - 使用当前工作目录
BGM_DIR = os.path.join(os.getcwd(), "backend", "seed", "bgm")


def migrate_bgm_to_tos():
    """将本地BGM上传到TOS并更新数据库"""

    # 1. 检查BGM目录
    if not os.path.exists(BGM_DIR):
        print(f"BGM目录不存在: {BGM_DIR}")
        return

    bgm_files = [f for f in os.listdir(BGM_DIR) if f.endswith(('.mp3', '.wav', '.flac'))]
    print(f"找到 {len(bgm_files)} 个BGM文件")

    if not bgm_files:
        print("没有需要迁移的BGM文件")
        return

    # 2. 获取TOS客户端
    try:
        tos_client = get_storage_client()
        print("TOS客户端初始化成功")
    except Exception as e:
        print(f"TOS客户端初始化失败: {e}")
        return

    # 3. 连接数据库
    db = SessionLocal()

    try:
        migrated = 0
        skipped = 0
        errors = []

        for filename in bgm_files:
            local_path = os.path.join(BGM_DIR, filename)
            print(f"\n处理: {filename}")

            # 4. 检查数据库中是否已存在
            # BGM的url字段存储的是本地相对路径
            local_url = f"backend/seed/bgm/{filename}"
            result = db.execute(
                text("SELECT id, url FROM assets WHERE url = :url AND type = 3"),
                {"url": local_url}
            )
            asset = result.fetchone()

            if not asset:
                print(f"  数据库中未找到记录，跳过")
                skipped += 1
                continue

            asset_id, old_url = asset
            print(f"  找到记录: id={asset_id}, url={old_url}")

            # 5. 如果已经是TOS URL，跳过
            if old_url and old_url.startswith("http"):
                print(f"  已经是TOS URL，跳过")
                skipped += 1
                continue

            # 6. 上传到TOS
            try:
                ext = os.path.splitext(filename)[1].lstrip(".")
                uuid_str = str(uuid.uuid4()).replace("-", "")
                object_name = f"materials/audio/bgm/{uuid_str[:2]}/{uuid_str[2:4]}/{uuid_str}.{ext}"

                tos_url = tos_client.upload_file(local_path, object_name)
                print(f"  上传成功: {tos_url}")

                # 7. 更新数据库
                db.execute(
                    text("UPDATE assets SET url = :new_url WHERE id = :id"),
                    {"new_url": tos_url, "id": asset_id}
                )
                db.commit()
                print(f"  数据库已更新")
                migrated += 1

            except Exception as e:
                error_msg = f"上传失败: {e}"
                print(f"  {error_msg}")
                errors.append(f"{filename}: {error_msg}")
                db.rollback()

        # 8. 输出统计
        print("\n" + "=" * 50)
        print("迁移完成!")
        print(f"  成功: {migrated}")
        print(f"  跳过: {skipped}")
        print(f"  失败: {len(errors)}")
        if errors:
            print("\n失败详情:")
            for err in errors:
                print(f"  - {err}")

    finally:
        db.close()


def verify_migration():
    """验证迁移结果"""
    db = SessionLocal()

    try:
        # 查询所有BGM资产
        result = db.execute(
            text("SELECT id, title, url, tags FROM assets WHERE type = 3 AND scope = 'bgm_library'")
        )
        assets = result.fetchall()

        print(f"\nBGM库中共 {len(assets)} 条记录:")
        for asset_id, title, url, tags in assets:
            url_type = "TOS" if url and url.startswith("http") else "本地"
            print(f"  [{url_type}] id={asset_id}, title={title[:30]}, url={url[:50] if url else 'None'}...")

    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("BGM迁移工具：本地 -> TOS")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_migration()
    else:
        migrate_bgm_to_tos()
        print("\n验证迁移结果:")
        verify_migration()
