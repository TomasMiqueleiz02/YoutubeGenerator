from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "YouTube AI Clip Generator"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/clip_generator"

    # Redis / Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # CORS / hosts
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # Storage
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    LOCAL_STORAGE_PATH: str = "./storage"
    S3_BUCKET_NAME: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    # S3-compatible providers (Railway buckets, R2, MinIO) need a custom
    # endpoint. Leave empty to talk to real AWS S3.
    AWS_ENDPOINT_URL: str = ""

    # yt-dlp: YouTube blocks downloads from datacenter IPs (Railway included)
    # unless requests carry cookies from a logged-in browser session. Export
    # cookies.txt (Netscape format) from a real YouTube session and paste its
    # full contents into this variable.
    YTDLP_COOKIES_CONTENT: str = ""

    # Semantic clip selection. Without a key the pipeline falls back to
    # audio/video energy heuristics, which find noise rather than meaning.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-5"
    WHISPER_MODEL_SIZE: str = "base"

    # Social APIs
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    INSTAGRAM_APP_ID: str = ""
    INSTAGRAM_APP_SECRET: str = ""
    YOUTUBE_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
