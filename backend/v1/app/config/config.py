"""应用配置管理"""
import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "VidMuse"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # MySQL 数据库
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "aigc_video"
    MYSQL_USER: str = "aigc_user"
    MYSQL_ROOT: str = "root"
    MYSQL_ROOT_PASSWORD: str = "root_password"
    MYSQL_PASSWORD: str = "123456"
    DATABASE_URL: str | None = None  # 显式指定时优先

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+aiomysql://{self.MYSQL_ROOT}:{self.MYSQL_ROOT_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )

    @property
    def sync_db_url(self) -> str:
        """Alembic 使用的同步连接串"""
        if self.DATABASE_URL:
            return self.DATABASE_URL.replace("+aiomysql", "+pymysql")
        return (
            f"mysql+pymysql://{self.MYSQL_ROOT}:{self.MYSQL_ROOT_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )

    # Redis / Celery 消息队列
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

    # MinIO 对象存储
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "aigc-videos"
    MINIO_SECURE: bool = False

    # 向量数据库配置
    VECTOR_DB_TYPE: str = "qdrant"  # 可选值: qdrant

    # ChromaDB
    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8001
    CHROMADB_SLICE_COLLECTION: str = "slice_knowledge"
    CHROMADB_VIDEO_COLLECTION: str = "video_knowledge"

    # Qdrant配置
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333  # HTTP端口
    QDRANT_GRPC_PORT: int = 6334  # gRPC端口
    QDRANT_API_KEY: str = "123456"
    QDRANT_PREFER_GRPC: bool = False
    QDRANT_COLLECTION: str = "video_knowledge"  # 默认集合

    # 这两个向量是生产者
    # slice包含视觉 + 动作 等域信息也就是因子
    QDRANT_SLICE_COLLECTION: str = "slice_knowledge"
    # video包含完整的骨架信息也就是策略
    QDRANT_VIDEO_COLLECTION: str = "video_knowledge"



    QDRANT_VECTOR_DIMENSION: int = 2048  # 使用与嵌入模型一致的维度

    # OpenAI
    OPENAI_API_KEY: str = ""

    # 火山引擎（豆包）
    DOUBAO_SEED_API_KEY: str = ""
    DOUBAO_SEED: str = "doubao-1.5-pro"
    DOUBAO_SEEDDANCE: str = "Doubao-Seedance-1.5-pro"
    VOLC_EMBEDDING_API_KEY: str = ""
    VOLC_EMBEDDING_MODEL: str = "bge-large-zh"
    VOLC_EMBEDDING_DIMENSION: int = 2048

    # 存储配置
    STORAGE_TYPE: str = "tos"  # 可选值: minio, tos, local
    LOCAL_STORAGE_ROOT: str = "local_uploads"
    LOCAL_STORAGE_URL_PREFIX: str = "/uploads"

    # 火山引擎对象存储 TOS
    TOS_ENDPOINT: str = "tos-cn-beijing.volces.com"
    TOS_ACCESS_KEY: str = os.getenv('TOS_ACCESS_KEY', '')
    TOS_SECRET_KEY: str = os.getenv('TOS_SECRET_KEY', '')
    TOS_BUCKET_NAME: str = "vidmuse"
    TOS_REGION: str = "cn-beijing"
    TOS_SECURE: bool = True

    # 火山引擎 TTS 语音合成
    TTS_ACCESS_KEY: str = ""
    TTS_SECRET_KEY: str = ""
    TTS_API_KEY: str = ""  # 新版语音合成API Key

    # 火山引擎图片生成 (Seedream 4.5)
    IMAGE_API_KEY: str = ""

    # 火山引擎语音识别
    VOLC_ENGINE_ACCESS_KEY: str = os.getenv('VOLC_ENGINE_ACCESS_KEY', '')
    VOLC_ENGINE_SECRET_KEY: str = os.getenv('VOLC_ENGINE_SECRET_KEY', '')
    VOLC_ENGINE_ASR_ENDPOINT: str = os.getenv('VOLC_ENGINE_ASR_ENDPOINT', 'https://openspeech.bytedance.com/api/v1/asr')
    VOLC_ENGINE_AUDIO_CLASSIFICATION_ENDPOINT: str = os.getenv('VOLC_ENGINE_AUDIO_CLASSIFICATION_ENDPOINT', 'https://openspeech.bytedance.com/api/v1/audio/classification')

    # FFmpeg 视频处理
    FFMPEG_PATH: str = ""
    FFPROBE_PATH: str = ""

    # Suno 音乐生成
    SUNO_API_KEY: str = ""



    # 上传配置
    UPLOAD_MAX_SIZE: int = 1024 * 1024 * 1024  # 1GB
    ALLOWED_EXTENSIONS: dict = {
        1: ["jpg", "jpeg", "png", "gif", "webp"],       # 图片
        2: ["mp4", "avi", "mov", "flv", "wmv", "webm"],  # 视频
        3: ["mp3", "wav", "flac", "aac", "ogg"]           # 音频
    }

    # JWT 配置
    JWT_SECRET_KEY: str = "vidmuse-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_SECONDS: int = 7200  # 2小时

    # 接口并发限制配置
    CONCURRENCY_LIMIT_ENABLED: bool = True  # 并发限制总开关
    CONCURRENCY_LIMIT_DEFAULT: int = 5  # 每个接口默认最大并发数
    CONCURRENCY_LIMIT_TIMEOUT: int = 30  # 排队超时时间（秒）
    CONCURRENCY_LIMIT_CUSTOM: dict = {}  # 自定义接口并发数，格式：{"/v1/api/path": 并发数}
    CONCURRENCY_LIMIT_EXCLUDE_PATHS: list = ["/", "/docs", "/openapi.json", "/redoc"]  # 不需要限流的路径

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
