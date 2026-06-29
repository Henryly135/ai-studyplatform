from app.core.config import settings
from app.core.logging import configure_logging
from platform_common.tasking.celery_app import build_celery_app


configure_logging()


celery_app = build_celery_app(
    app_name="ai_service",
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    include=[
        "app.tasks.smoke",
        "app.tasks.material_index",
        "app.tasks.recover_stale_jobs",
        "app.tasks.quiz_generation",
    ],
    app_timezone=settings.app_timezone,
    task_default_queue=settings.celery_task_default_queue,
    broker_connection_retry_on_startup=settings.celery_broker_connection_retry_on_startup,
    task_always_eager=settings.celery_task_always_eager,
    worker_concurrency=settings.celery_worker_concurrency,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    result_expires=settings.celery_result_expires,
)

celery_app.conf.beat_schedule = {
    "recover-stale-ai-index-jobs": {
        "task": "app.tasks.recover_stale_jobs.recover_stale_index_jobs_task",
        "schedule": max(1, settings.ai_index_job_reaper_interval_seconds),
        "options": {"queue": settings.celery_task_default_queue},
    }
}
