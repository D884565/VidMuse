"""同步数据库连接（RAG 模块使用）"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.v1.app.config.config import settings
# 复用 async_database 的 Base，确保模型元数据一致
from backend.store.database.async_database import Base

engine = create_engine(
    settings.sync_db_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.APP_ENV == "development"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """获取同步数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
