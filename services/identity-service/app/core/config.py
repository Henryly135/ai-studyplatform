from dataclasses import dataclass
from platform_common.config import get_env, load_project_env

load_project_env(__file__)


@dataclass(frozen=True)
class Settings:
    app_timezone: str = get_env("APP_TIMEZONE", default="Australia/Sydney")
    identity_port: int = int(get_env("IDENTITY_PORT", default="8000"))
    celery_broker_url: str = get_env("CELERY_BROKER_URL", default="redis://redis:6379/0")
    celery_result_backend: str = get_env("CELERY_RESULT_BACKEND", default="redis://redis:6379/0")
    celery_task_always_eager: bool = get_env("CELERY_TASK_ALWAYS_EAGER", default="false").lower() == "true"
    celery_task_default_queue: str = get_env("IDENTITY_CELERY_TASK_DEFAULT_QUEUE", default="identity.default")
    celery_worker_concurrency: int = int(get_env("CELERY_WORKER_CONCURRENCY", default="2"))
    celery_task_time_limit: int = int(get_env("CELERY_TASK_TIME_LIMIT", default="300"))
    celery_task_soft_time_limit: int = int(get_env("CELERY_TASK_SOFT_TIME_LIMIT", default="240"))
    celery_result_expires: int = int(get_env("CELERY_RESULT_EXPIRES", default="3600"))
    celery_broker_connection_retry_on_startup: bool = get_env(
        "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP",
        default="true",
    ).lower() == "true"
    educator_approval_notification_queue: str = get_env(
        "COMMUNICATION_CELERY_TASK_DEFAULT_QUEUE",
        default="communication.notifications",
    )
    ai_service_url: str = get_env("AI_SERVICE_URL", default="http://ai-service:8001")
    db_host: str = get_env("IDENTITY_DB_HOST", "DB_HOST", default="mysql")
    db_port: int = int(get_env("IDENTITY_DB_PORT", "DB_PORT", default="3306"))
    db_user: str = get_env("IDENTITY_DB_USER", "DB_USER", default="app_user")
    db_password: str = get_env("IDENTITY_DB_PASSWORD", "DB_PASSWORD", default="app_password")
    db_name: str = get_env("IDENTITY_DB_NAME", "DB_NAME", default="identity_db")
    db_echo: bool = get_env("IDENTITY_DB_ECHO", "DB_ECHO", default="false").lower() == "true"
    db_pool_pre_ping: bool = get_env(
        "IDENTITY_DB_POOL_PRE_PING",
        "DB_POOL_PRE_PING",
        default="true",
    ).lower() == "true"
    public_id_secret: str = get_env("PUBLIC_ID_SECRET", default="")
    public_id_secret_fallback: str = get_env(
        "JWT_SECRET_KEY",
        default="change-me-in-production-use-a-long-random-string",
    )
    jwt_secret_key: str = get_env("JWT_SECRET_KEY", default="change-me-in-production-use-a-long-random-string")
    jwt_algorithm: str = get_env("JWT_ALGORITHM", default="HS256")
    jwt_expire_minutes: int = int(get_env("JWT_EXPIRE_MINUTES", default="60"))
    email_verification_token_expire_hours: int = int(
        get_env("EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS", default="24")
    )
    password_reset_token_expire_minutes: int = int(
        get_env("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", default="60")
    )
    internal_api_token: str = get_env("INTERNAL_API_TOKEN", default="")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def jwt_expire_seconds(self) -> int:
        return self.jwt_expire_minutes * 60


settings = Settings()
