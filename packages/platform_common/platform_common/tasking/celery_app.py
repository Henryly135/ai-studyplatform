from collections.abc import Sequence

from celery import Celery

from platform_common.tasking.celery_config import build_celery_config


def build_celery_app(
    *,
    app_name: str,
    broker_url: str,
    result_backend: str,
    include: Sequence[str],
    app_timezone: str,
    task_default_queue: str,
    broker_connection_retry_on_startup: bool,
    task_always_eager: bool,
    worker_concurrency: int,
    task_time_limit: int,
    task_soft_time_limit: int,
    result_expires: int,
) -> Celery:
    celery_app = Celery(
        app_name,
        broker=broker_url,
        backend=result_backend,
        include=list(include),
    )
    celery_app.conf.update(
        build_celery_config(
            app_timezone=app_timezone,
            task_default_queue=task_default_queue,
            broker_connection_retry_on_startup=broker_connection_retry_on_startup,
            task_always_eager=task_always_eager,
            worker_concurrency=worker_concurrency,
            task_time_limit=task_time_limit,
            task_soft_time_limit=task_soft_time_limit,
            result_expires=result_expires,
        )
    )
    return celery_app
