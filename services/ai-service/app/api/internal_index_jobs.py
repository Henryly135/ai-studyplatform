from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.index_jobs import (
    MaterialIndexDeleteRequest,
    MaterialIndexDeleteResponse,
    MaterialIndexJobRegisterRequest,
    MaterialIndexJobRegisterResponse,
    RecoverStaleIndexJobsResponse,
    ReleaseIndexJobsRequest,
    ReleaseIndexJobsResponse,
    RetryIndexJobResponse,
)
from app.services.indexing.index_job_service import IndexJobService


router = APIRouter(prefix="/internal/index-jobs", tags=["internal-index-jobs"])


@router.post("/material", response_model=MaterialIndexJobRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_material_index_job(
    payload: MaterialIndexJobRegisterRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> MaterialIndexJobRegisterResponse:
    return IndexJobService(session).register_material_job(payload=payload)


@router.post("/material/delete", response_model=MaterialIndexDeleteResponse)
def delete_material_index(
    payload: MaterialIndexDeleteRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> MaterialIndexDeleteResponse:
    return IndexJobService(session).delete_material_index(payload=payload)


@router.post("/release", response_model=ReleaseIndexJobsResponse)
def release_blocked_index_jobs(
    payload: ReleaseIndexJobsRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> ReleaseIndexJobsResponse:
    return IndexJobService(session).release_blocked_jobs(payload=payload)


@router.post("/{job_id}/retry", response_model=RetryIndexJobResponse)
def retry_index_job(
    job_id: int,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> RetryIndexJobResponse:
    return IndexJobService(session).retry_job(job_id=job_id)


@router.post("/recover-stale", response_model=RecoverStaleIndexJobsResponse)
def recover_stale_index_jobs(
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> RecoverStaleIndexJobsResponse:
    return IndexJobService(session).recover_stale_running_jobs()
