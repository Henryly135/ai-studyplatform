from dataclasses import dataclass
from pathlib import Path
from platform_common.config import get_env, load_project_env

load_project_env(__file__)

DEFAULT_MINIO_ENDPOINT = f"http://minio:{get_env('MINIO_API_PORT', default='9000')}"
DEFAULT_REDIS_HOST = get_env("REDIS_HOST", default="redis")
DEFAULT_REDIS_PORT = get_env("REDIS_PORT", "REDIS_INTERNAL_PORT", default="")
DEFAULT_REDIS_DB = get_env("REDIS_DB", default="0")
DEFAULT_CELERY_BROKER_URL = f"redis://{DEFAULT_REDIS_HOST}:{DEFAULT_REDIS_PORT}/{DEFAULT_REDIS_DB}"


@dataclass(frozen=True)
class Settings:
    app_timezone: str = get_env("APP_TIMEZONE", default="Australia/Sydney")
    ai_service_port: int = int(get_env("AI_SERVICE_PORT", default="8001"))
    ai_db_host: str = get_env("AI_DB_HOST", default="postgres-ai")
    ai_db_port: int = int(get_env("AI_DB_PORT", default="5432"))
    ai_db_user: str = get_env("AI_DB_USER", default="ai_user")
    ai_db_password: str = get_env("AI_DB_PASSWORD", default="ai_password")
    ai_db_name: str = get_env("AI_DB_NAME", default="learning_platform_ai")
    ai_db_echo: bool = get_env("AI_DB_ECHO", default="false").lower() == "true"
    ai_db_pool_pre_ping: bool = get_env("AI_DB_POOL_PRE_PING", default="true").lower() == "true"
    ai_embedding_provider: str = get_env("AI_EMBEDDING_PROVIDER", default="gemini")
    ai_embedding_model: str = get_env("AI_EMBEDDING_MODEL", default="gemini-embedding-001")
    ai_embedding_dimension: int = int(get_env("AI_EMBEDDING_DIMENSION", default="1536"))
    ai_embedding_output_dimension: int = int(get_env("AI_EMBEDDING_OUTPUT_DIMENSION", default="1536"))
    ai_embedding_task_type: str = get_env("AI_EMBEDDING_TASK_TYPE", default="RETRIEVAL_DOCUMENT")
    ai_embedding_version: str = get_env("AI_EMBEDDING_VERSION", default="gemini-embedding-001@1536")
    ai_embedding_batch_size: int = int(get_env("AI_EMBEDDING_BATCH_SIZE", default="16"))
    ai_embedding_orchestrator: str = get_env("AI_EMBEDDING_ORCHESTRATOR", default="langchain")
    ai_chunk_size_chars: int = int(get_env("AI_CHUNK_SIZE_CHARS", default="1200"))
    ai_chunk_overlap_chars: int = int(get_env("AI_CHUNK_OVERLAP_CHARS", default="200"))
    ai_retrieval_top_k: int = int(get_env("AI_RETRIEVAL_TOP_K", default="5"))
    ai_retrieval_min_score: float = float(get_env("AI_RETRIEVAL_MIN_SCORE", default="0.45"))
    ai_chat_max_output_tokens: int = int(get_env("AI_CHAT_MAX_OUTPUT_TOKENS", default="900"))
    ai_chat_orchestrator: str = get_env("AI_CHAT_ORCHESTRATOR", default="langchain")
    ai_index_job_max_auto_retries: int = int(get_env("AI_INDEX_JOB_MAX_AUTO_RETRIES", default="3"))
    ai_index_job_retry_base_seconds: int = int(get_env("AI_INDEX_JOB_RETRY_BASE_SECONDS", default="30"))
    ai_index_job_retry_max_seconds: int = int(get_env("AI_INDEX_JOB_RETRY_MAX_SECONDS", default="900"))
    ai_index_job_running_timeout_seconds: int = int(get_env("AI_INDEX_JOB_RUNNING_TIMEOUT_SECONDS", default="1800"))
    ai_index_job_reaper_interval_seconds: int = int(get_env("AI_INDEX_JOB_REAPER_INTERVAL_SECONDS", default="60"))
    identity_service_url: str = get_env("IDENTITY_SERVICE_URL", default="http://identity-service:8000")
    ai_service_url: str = get_env("AI_SERVICE_URL", default="http://ai-service:8001")
    communication_service_url: str = get_env("COMMUNICATION_SERVICE_URL", default="http://communication-service:8002")
    learning_service_url: str = get_env("LEARNING_SERVICE_URL", default="http://learning-service:8003")
    redis_host: str = DEFAULT_REDIS_HOST
    redis_port: int = int(DEFAULT_REDIS_PORT)
    redis_db: int = int(DEFAULT_REDIS_DB)
    celery_broker_url: str = get_env("CELERY_BROKER_URL", default=DEFAULT_CELERY_BROKER_URL)
    celery_result_backend: str = get_env("CELERY_RESULT_BACKEND", default=DEFAULT_CELERY_BROKER_URL)
    celery_task_always_eager: bool = get_env("CELERY_TASK_ALWAYS_EAGER", default="false").lower() == "true"
    celery_task_default_queue: str = get_env("CELERY_TASK_DEFAULT_QUEUE", default="ai.default")
    learning_material_ai_queue: str = get_env("LEARNING_MATERIAL_AI_QUEUE", default="ai.material.index")
    celery_worker_concurrency: int = int(get_env("CELERY_WORKER_CONCURRENCY", default="2"))
    celery_task_time_limit: int = int(get_env("CELERY_TASK_TIME_LIMIT", default="300"))
    celery_task_soft_time_limit: int = int(get_env("CELERY_TASK_SOFT_TIME_LIMIT", default="240"))
    celery_result_expires: int = int(get_env("CELERY_RESULT_EXPIRES", default="3600"))
    celery_broker_connection_retry_on_startup: bool = get_env(
        "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP",
        default="true",
    ).lower() == "true"
    object_storage_provider: str = get_env("OBJECT_STORAGE_PROVIDER", default="local")
    minio_endpoint: str = get_env("MINIO_ENDPOINT", default=DEFAULT_MINIO_ENDPOINT)
    minio_access_key: str = get_env("MINIO_ACCESS_KEY", default="minioadmin")
    minio_secret_key: str = get_env("MINIO_SECRET_KEY", default="minioadmin")
    minio_bucket: str = get_env("MINIO_BUCKET", default="learning-materials")
    ai_profile_bucket: str = get_env("AI_PROFILE_BUCKET", default="ai-profile-assets")
    minio_public_base_url: str = get_env("MINIO_PUBLIC_BASE_URL", default="")
    minio_signed_url_expires_seconds: int = int(get_env("MINIO_SIGNED_URL_EXPIRES_SECONDS", default="300"))
    ai_profile_root_path: str = get_env(
        "AI_PROFILE_ROOT_PATH",
        default=str((Path(__file__).resolve().parents[2] / ".data" / "ai-profile-assets").resolve()),
    )
    gemini_api_key: str = get_env("GEMINI_API_KEY", default="")
    ai_demo_model_name: str = get_env("AI_DEMO_MODEL_NAME", "MODEL_NAME", default="gemini-2.5-flash")
    langgraph_checkpoint_enabled: bool = get_env("LANGGRAPH_CHECKPOINT_ENABLED", default="true").lower() == "true"
    langgraph_checkpoint_redis_url: str = get_env(
        "LANGGRAPH_CHECKPOINT_REDIS_URL",
        default=f"redis://{DEFAULT_REDIS_HOST}:{DEFAULT_REDIS_PORT}/1",
    )
    langgraph_checkpoint_key_prefix: str = get_env("LANGGRAPH_CHECKPOINT_KEY_PREFIX", default="ai.langgraph")
    quiz_generation_run_redis_url: str = get_env(
        "QUIZ_GENERATION_RUN_REDIS_URL",
        default=get_env(
            "LANGGRAPH_CHECKPOINT_REDIS_URL",
            default=f"redis://{DEFAULT_REDIS_HOST}:{DEFAULT_REDIS_PORT}/1",
        ),
    )
    quiz_generation_run_key_prefix: str = get_env("QUIZ_GENERATION_RUN_KEY_PREFIX", default="ai.quiz_generation")
    quiz_generation_run_ttl_seconds: int = int(get_env("QUIZ_GENERATION_RUN_TTL_SECONDS", default="3600"))
    internal_api_token: str = get_env("INTERNAL_API_TOKEN", default="")
    public_id_secret: str = get_env("PUBLIC_ID_SECRET", default="")
    public_id_secret_fallback: str = get_env(
        "JWT_SECRET_KEY",
        default="change-me-in-production-use-a-long-random-string",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.ai_db_user}:{self.ai_db_password}"
            f"@{self.ai_db_host}:{self.ai_db_port}/{self.ai_db_name}"
        )


settings = Settings()
