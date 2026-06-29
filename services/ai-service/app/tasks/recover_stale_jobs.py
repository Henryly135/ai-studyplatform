from app.db.session import SessionLocal
from app.core.celery_app import celery_app
from app.services.indexing.index_job_service import IndexJobService


@celery_app.task(name="app.tasks.recover_stale_jobs.recover_stale_index_jobs_task")
def recover_stale_index_jobs_task() -> dict[str, object]:
    session = SessionLocal()
    try:
        response = IndexJobService(session).recover_stale_running_jobs()
        return {
            "status": "accepted",
            "recoveredJobIds": response.recoveredJobIds,
            "recoveredCount": response.recoveredCount,
            "dispatchedCount": response.dispatchedCount,
        }
    finally:
        session.close()
