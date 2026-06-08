#!/usr/bin/env python3
"""
重置用户密码脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from backend.v1.app.config.config import settings

def reset_user_password(username, new_password):
    """重置用户密码"""
    engine = create_engine(settings.sync_db_url)
    with engine.connect() as conn:
        result = conn.execute(
            text("UPDATE users SET password_hash = :password WHERE username = :username"),
            {"password": new_password, "username": username}
        )
        conn.commit()
        if result.rowcount > 0:
            print(f"用户 {username} 密码已成功重置为: {new_password}")
        else:
            print(f"用户 {username} 不存在！")

if __name__ == "__main__":
    reset_user_password("admin", "admin123")
