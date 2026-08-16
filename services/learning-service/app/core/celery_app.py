from app.core.config import settings
from platform_common.tasking.celery_app import build_celery_app


celery_app = build_celery_app(
    app_name="learning_service",
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    include=["app.tasks.quiz_attempts", "app.tasks.material_index_registration"],
    app_timezone=settings.app_timezone,
    task_default_queue=settings.celery_task_default_queue,
    broker_connection_retry_on_startup=settings.celery_broker_connection_retry_on_startup,
    task_always_eager=settings.celery_task_always_eager,
    worker_concurrency=settings.celery_worker_concurrency,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    result_expires=settings.celery_result_expires,
)
