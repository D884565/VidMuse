"""同步数据库连接（RAG 模块使用）"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.v1.app.config.config import settings

engine = create_engine(
    settings.sync_db_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.APP_ENV == "development"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取同步数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
