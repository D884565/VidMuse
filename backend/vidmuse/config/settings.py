import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", 8000))

    # MySQL 配置
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "aigc_video")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "aigc_user")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "aigc_password")

    # MinIO 配置
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "aigc-videos")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # ChromaDB 配置
    CHROMADB_HOST: str = os.getenv("CHROMADB_HOST", "localhost")
    CHROMADB_PORT: int = int(os.getenv("CHROMADB_PORT", 8001))
    CHROMADB_COLLECTION: str = os.getenv("CHROMADB_COLLECTION", "video_embeddings")
    CHROMADB_TENANT: str = os.getenv("CHROMADB_TENANT", "default_tenant")
    CHROMADB_DATABASE: str = os.getenv("CHROMADB_DATABASE", "default_database")

    # 上传配置
    UPLOAD_MAX_SIZE: int = 1024 * 1024 * 1024  # 1GB
    ALLOWED_EXTENSIONS: dict = {
        1: ["jpg", "jpeg", "png", "gif", "webp"],  # 图片
        2: ["mp4", "avi", "mov", "flv", "wmv", "webm"],  # 视频
        3: ["mp3", "wav", "flac", "aac", "ogg"]  # 音频
    }

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        """数据库连接URL"""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"


settings = Settings()