from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_identity_user
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import get_db_session
from app.repositories.ai_index_jobs_repository import AIIndexJobsRepository
from app.schemas.tasks import (
    IndexJobStatusResponse,
    SmokeTaskEnqueueResponse,
    SmokeTaskRequest,
    SmokeTaskResultResponse,
)
from app.tasks.smoke import ping_task
from platform_common.errors import http_error


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/smoke", response_model=SmokeTaskEnqueueResponse)
def enqueue_smoke_task(
    payload: SmokeTaskRequest,
    current_user: dict = Depends(require_identity_user),
) -> SmokeTaskEnqueueResponse:
    task = ping_task.delay(payload.message.strip())
    return SmokeTaskEnqueueResponse(
        task_id=task.id,
        queue=settings.celery_task_default_queue,
        requested_by=int(current_user["id"]),
        status="queued",
    )


@router.get("/smoke/{task_id}", response_model=SmokeTaskResultResponse)
def get_smoke_task_result(
    task_id: str,
    _: dict = Depends(require_identity_user),
) -> SmokeTaskResultResponse:
    task_result = celery_app.AsyncResult(task_id)
    if task_result.status == "PENDING":
        return SmokeTaskResultResponse(task_id=task_id, status="pending")
    if task_result.status == "STARTED":
        return SmokeTaskResultResponse(task_id=task_id, status="started")
    if task_result.status == "SUCCESS":
        result = task_result.result if isinstance(task_result.result, dict) else {"value": task_result.result}
        return SmokeTaskResultResponse(task_id=task_id, status="success", result=result)
    if task_result.status == "FAILURE":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "TASK_EXECUTION_FAILED",
                "message": str(task_result.result),
            },
        )
    return SmokeTaskResultResponse(task_id=task_id, status=task_result.status.lower())


@router.get("/index-jobs/{job_id}", response_model=IndexJobStatusResponse)
def get_index_job_status(
    job_id: int,
    _: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> IndexJobStatusResponse:
    job = AIIndexJobsRepository(session).get_by_id(job_id)
    if job is None:
        raise http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INDEX_JOB_NOT_FOUND",
            message="Index job not found",
        )

    return IndexJobStatusResponse(
        job_id=job.job_id,
        job_type=job.job_type.value,
        source_type=job.source_type.value,
        source_ref_id=job.source_ref_id,
        course_id=job.course_id,
        module_id=job.module_id,
        material_id=job.material_id,
        status=job.status.value,
        priority=job.priority,
        attempt_count=job.attempt_count,
        error_message=job.error_message,
        worker_id=job.worker_id,
        next_retry_at=job.next_retry_at,
        locked_at=job.locked_at,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
