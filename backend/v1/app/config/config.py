"""应用配置管理"""
import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "VidMuse"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "aigc_video"
    MYSQL_USER: str = "aigc_user"
    MYSQL_PASSWORD: str = "aigc_password"
    DATABASE_URL: str | None = None  # 显式指定时优先

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )

    @property
    def sync_db_url(self) -> str:
        """Alembic 使用的同步连接串"""
        if self.DATABASE_URL:
            return self.DATABASE_URL.replace("+aiomysql", "+pymysql")
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )

    # Redis / Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    @property
    def celery_broker(self) -> str:
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def celery_backend(self) -> str:
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "aigc-videos"
    MINIO_SECURE: bool = False

    # ChromaDB
    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8001
    CHROMADB_COLLECTION: str = "video_knowledge"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # 火山引擎（豆包）
    DOUBAO_SEED_API_KEY: str = ""
    DOUBAO_SEED: str = "doubao-1.5-pro"
    DOUBAO_SEEDDANCE: str = "doubao-1.5-pro"
    VOLC_EMBEDDING_API_KEY: str = ""
    VOLC_EMBEDDING_MODEL: str = "bge-large-zh"
    VOLC_EMBEDDING_DIMENSION: int = 2048

    # 存储配置
    STORAGE_TYPE: str = "minio"  # 可选值: minio, tos

    # 火山引擎对象存储 TOS
    TOS_ENDPOINT: str = "tos-cn-beijing.volces.com"
    TOS_ACCESS_KEY: str = os.getenv('TOS_ACCESS_KEY')
    TOS_SECRET_KEY: str = os.getenv('TOS_SECRET_KEY')
    TOS_BUCKET_NAME: str = "vidmuse"
    TOS_REGION: str = "cn-beijing"
    TOS_SECURE: bool = True

    # 火山引擎 TTS 语音合成
    TTS_ACCESS_KEY: str = ""
    TTS_SECRET_KEY: str = ""

    # 上传配置
    UPLOAD_MAX_SIZE: int = 1024 * 1024 * 1024  # 1GB
    ALLOWED_EXTENSIONS: dict = {
        1: ["jpg", "jpeg", "png", "gif", "webp"],       # 图片
        2: ["mp4", "avi", "mov", "flv", "wmv", "webm"],  # 视频
        3: ["mp3", "wav", "flac", "aac", "ogg"]           # 音频
    }

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
