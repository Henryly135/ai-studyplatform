from dataclasses import dataclass
from platform_common.config import get_env, load_project_env

load_project_env(__file__)


@dataclass(frozen=True)
class Settings:
    communication_port: int = int(get_env("COMMUNICATION_PORT", default="8002"))
    app_timezone: str = get_env("APP_TIMEZONE", default="Australia/Sydney")
    identity_service_url: str = get_env("IDENTITY_SERVICE_URL", default="http://identity-service:8000")
    learning_service_url: str = get_env("LEARNING_SERVICE_URL", default="http://learning-service:8003")
    celery_broker_url: str = get_env("CELERY_BROKER_URL", default="redis://redis:6379/0")
    celery_result_backend: str = get_env("CELERY_RESULT_BACKEND", default="redis://redis:6379/0")
    celery_task_always_eager: bool = get_env("CELERY_TASK_ALWAYS_EAGER", default="false").lower() == "true"
    celery_task_default_queue: str = get_env(
        "COMMUNICATION_CELERY_TASK_DEFAULT_QUEUE",
        default="communication.notifications",
    )
    celery_worker_concurrency: int = int(get_env("CELERY_WORKER_CONCURRENCY", default="2"))
    celery_task_time_limit: int = int(get_env("CELERY_TASK_TIME_LIMIT", default="300"))
    celery_task_soft_time_limit: int = int(get_env("CELERY_TASK_SOFT_TIME_LIMIT", default="240"))
    celery_result_expires: int = int(get_env("CELERY_RESULT_EXPIRES", default="3600"))
    celery_broker_connection_retry_on_startup: bool = get_env(
        "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP",
        default="true",
    ).lower() == "true"
    db_host: str = get_env("COMMUNICATION_DB_HOST", "DB_HOST", default="mysql")
    db_port: int = int(get_env("COMMUNICATION_DB_PORT", "DB_PORT", default="3306"))
    db_user: str = get_env("COMMUNICATION_DB_USER", "DB_USER", default="app_user")
    db_password: str = get_env("COMMUNICATION_DB_PASSWORD", "DB_PASSWORD", default="app_password")
    db_name: str = get_env("COMMUNICATION_DB_NAME", "DB_NAME", default="communication_db")
    db_echo: bool = get_env(
        "COMMUNICATION_DB_ECHO",
        "DB_ECHO",
        default="false",
    ).lower() == "true"
    db_pool_pre_ping: bool = get_env(
        "COMMUNICATION_DB_POOL_PRE_PING",
        "DB_POOL_PRE_PING",
        default="true",
    ).lower() == "true"
    public_id_secret: str = get_env("PUBLIC_ID_SECRET", default="")
    public_id_secret_fallback: str = get_env(
        "JWT_SECRET_KEY",
        default="change-me-in-production-use-a-long-random-string",
    )
    internal_api_token: str = get_env("INTERNAL_API_TOKEN", default="")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
