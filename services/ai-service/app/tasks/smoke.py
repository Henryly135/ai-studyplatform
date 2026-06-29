from app.core.celery_app import celery_app
from app.core.time import now_local


@celery_app.task(name="app.tasks.smoke.ping_task")
def ping_task(payload: str = "pong") -> dict[str, str]:
    return {
        "message": payload,
        "processedAt": now_local().isoformat(timespec="seconds"),
    }
