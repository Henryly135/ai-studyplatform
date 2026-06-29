from dataclasses import dataclass
from pathlib import Path
from platform_common.config import get_env, load_project_env

load_project_env(__file__)

DEFAULT_MINIO_ENDPOINT = f"http://minio:{get_env('MINIO_API_PORT', default='9000')}"
DEFAULT_REDIS_HOST = get_env("REDIS_HOST", default="redis")
DEFAULT_REDIS_PORT = get_env("REDIS_PORT", "REDIS_INTERNAL_PORT", default="")
DEFAULT_REDIS_DB = get_env("REDIS_DB", default="0")
DEFAULT_CELERY_BROKER_URL = f"redis://{DEFAULT_REDIS_HOST}:{DEFAULT_REDIS_PORT}/{DEFAULT_REDIS_DB}"
DEFAULT_QUIZ_REDIS_HOST = get_env("QUIZ_REDIS_HOST", default="redis-quiz")
DEFAULT_QUIZ_REDIS_PORT = get_env("QUIZ_REDIS_PORT", "QUIZ_REDIS_INTERNAL_PORT", default="6379")
DEFAULT_QUIZ_REDIS_DB = get_env("QUIZ_REDIS_DB", default="0")
DEFAULT_QUIZ_REDIS_URL = f"redis://{DEFAULT_QUIZ_REDIS_HOST}:{DEFAULT_QUIZ_REDIS_PORT}/{DEFAULT_QUIZ_REDIS_DB}"


@dataclass(frozen=True)
class Settings:
    app_timezone: str = get_env("APP_TIMEZONE", default="Australia/Sydney")
    learning_port: int = int(get_env("LEARNING_PORT", default="8003"))
    public_base_url: str = get_env("PUBLIC_BASE_URL", default="")
    public_frontend_url: str = get_env("PUBLIC_FRONTEND_URL", default="")
    identity_service_url: str = get_env("IDENTITY_SERVICE_URL", default="http://identity-service:8000")
    ai_service_url: str = get_env("AI_SERVICE_URL", default="http://ai-service:8001")
    db_host: str = get_env("LEARNING_DB_HOST", "DB_HOST", default="mysql")
    db_port: int = int(get_env("LEARNING_DB_PORT", "DB_PORT", default="3306"))
    db_user: str = get_env("LEARNING_DB_USER", "DB_USER", default="app_user")
    db_password: str = get_env("LEARNING_DB_PASSWORD", "DB_PASSWORD", default="app_password")
    db_name: str = get_env("LEARNING_DB_NAME", "DB_NAME", default="learning_db")
    db_echo: bool = get_env("LEARNING_DB_ECHO", "DB_ECHO", default="false").lower() == "true"
    db_pool_pre_ping: bool = get_env(
        "LEARNING_DB_POOL_PRE_PING",
        "DB_POOL_PRE_PING",
        default="true",
    ).lower() == "true"
    celery_broker_url: str = get_env("CELERY_BROKER_URL", default=DEFAULT_CELERY_BROKER_URL)
    celery_result_backend: str = get_env("CELERY_RESULT_BACKEND", default=DEFAULT_CELERY_BROKER_URL)
    celery_task_always_eager: bool = get_env("CELERY_TASK_ALWAYS_EAGER", default="false").lower() == "true"
    celery_task_default_queue: str = get_env("CELERY_TASK_DEFAULT_QUEUE", default="ai.default")
    celery_worker_concurrency: int = int(get_env("CELERY_WORKER_CONCURRENCY", default="2"))
    celery_task_time_limit: int = int(get_env("CELERY_TASK_TIME_LIMIT", default="300"))
    celery_task_soft_time_limit: int = int(get_env("CELERY_TASK_SOFT_TIME_LIMIT", default="240"))
    celery_result_expires: int = int(get_env("CELERY_RESULT_EXPIRES", default="3600"))
    celery_broker_connection_retry_on_startup: bool = get_env(
        "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP",
        default="true",
    ).lower() == "true"
    quiz_redis_url: str = get_env("QUIZ_REDIS_URL", default=DEFAULT_QUIZ_REDIS_URL)
    quiz_attempt_session_grace_seconds: int = int(
        get_env("QUIZ_ATTEMPT_SESSION_GRACE_SECONDS", default="300")
    )
    quiz_attempt_session_fallback_ttl_seconds: int = int(
        get_env("QUIZ_ATTEMPT_SESSION_FALLBACK_TTL_SECONDS", default="7200")
    )
    quiz_attempt_submit_lock_seconds: int = int(
        get_env("QUIZ_ATTEMPT_SUBMIT_LOCK_SECONDS", default="60")
    )
    quiz_attempt_counter_ttl_seconds: int = int(
        get_env("QUIZ_ATTEMPT_COUNTER_TTL_SECONDS", default="2592000")
    )
    learning_material_root: str = get_env(
        "LEARNING_MATERIAL_ROOT",
        default="/app/storage/materials",
    )
    learning_material_public_base_url: str = get_env(
        "LEARNING_MATERIAL_PUBLIC_BASE_URL",
        default="/api/learning/materials",
    )
    learning_material_ai_queue: str = get_env(
        "LEARNING_MATERIAL_AI_QUEUE",
        default="ai.material.index",
    )
    object_storage_provider: str = get_env("OBJECT_STORAGE_PROVIDER", default="local")
    minio_endpoint: str = get_env("MINIO_ENDPOINT", default=DEFAULT_MINIO_ENDPOINT)
    minio_access_key: str = get_env("MINIO_ACCESS_KEY", default="minioadmin")
    minio_secret_key: str = get_env("MINIO_SECRET_KEY", default="minioadmin")
    minio_bucket: str = get_env("MINIO_BUCKET", default="learning-materials")
    minio_public_base_url: str = get_env("MINIO_PUBLIC_BASE_URL", default="")
    minio_signed_url_expires_seconds: int = int(get_env("MINIO_SIGNED_URL_EXPIRES_SECONDS", default="300"))
    minio_multipart_part_url_expires_seconds: int = int(
        get_env("MINIO_MULTIPART_PART_URL_EXPIRES_SECONDS", default="3600")
    )
    multipart_upload_session_ttl_seconds: int = int(
        get_env("MULTIPART_UPLOAD_SESSION_TTL_SECONDS", default="900")
    )
    internal_api_token: str = get_env("INTERNAL_API_TOKEN", default="")
    public_id_secret: str = get_env("PUBLIC_ID_SECRET", default="")
    public_id_secret_fallback: str = get_env(
        "JWT_SECRET_KEY",
        default="change-me-in-production-use-a-long-random-string",
    )

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def material_root_path(self) -> Path:
        return Path(self.learning_material_root).expanduser().resolve()


settings = Settings()
