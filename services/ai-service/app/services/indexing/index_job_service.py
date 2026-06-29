from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.time import now_local
from app.models.ai_index_jobs import AIJobStatus
from app.repositories.ai_index_jobs_repository import AIIndexJobsRepository
from app.schemas.index_jobs import MaterialIndexDeleteRequest, MaterialIndexDeleteResponse
from app.schemas.index_jobs import (
    MaterialIndexJobRegisterRequest,
    MaterialIndexJobRegisterResponse,
    RecoverStaleIndexJobsResponse,
    ReleaseIndexJobsRequest,
    ReleaseIndexJobsResponse,
    RetryIndexJobResponse,
)
from app.services.indexing.knowledge_indexing_service import KnowledgeIndexingService
from platform_common.errors import invalid_request_error


class IndexJobService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.jobs = AIIndexJobsRepository(session)
        self.knowledge = KnowledgeIndexingService(session)

    def register_material_job(self, *, payload: MaterialIndexJobRegisterRequest) -> MaterialIndexJobRegisterResponse:
        normalized_module_status = payload.moduleStatus.strip().lower()
        if normalized_module_status not in {"draft", "published", "archived"}:
            raise invalid_request_error("moduleStatus must be one of draft, published, archived")

        replaceable_jobs = self.jobs.list_replaceable_material_jobs(material_id=payload.materialId)
        if replaceable_jobs:
            self.jobs.mark_superseded(replaceable_jobs)

        target_status = AIJobStatus.QUEUED if normalized_module_status == "published" else AIJobStatus.BLOCKED
        job = self.jobs.create_material_job(
            source_ref_id=str(payload.materialId),
            course_id=payload.courseId,
            module_id=payload.moduleId,
            material_id=payload.materialId,
            source_version=payload.objectKey,
            content_hash=None,
            metadata_json={
                "educatorId": payload.educatorId,
                "title": payload.title,
                "materialType": payload.materialType,
                "resourceUrl": payload.resourceUrl,
                "storagePath": payload.storagePath,
                "absolutePath": payload.absolutePath,
                "contentType": payload.contentType,
                "sizeBytes": payload.sizeBytes,
                "moduleStatus": normalized_module_status,
                "storageProvider": payload.storageProvider,
                "storageBucket": payload.storageBucket,
                "objectKey": payload.objectKey,
            },
            status=target_status,
            priority=100,
            trigger_event_id=f"material:{payload.materialId}:upload",
        )
        self.session.commit()

        dispatched = False
        if job.status == AIJobStatus.QUEUED:
            self._dispatch_job(job.job_id)
            dispatched = True

        return MaterialIndexJobRegisterResponse(
            jobId=job.job_id,
            status=job.status.value,
            dispatched=dispatched,
        )

    def release_blocked_jobs(self, *, payload: ReleaseIndexJobsRequest) -> ReleaseIndexJobsResponse:
        blocked_jobs = self.jobs.list_blocked_jobs_for_modules(
            course_id=payload.courseId,
            module_ids=payload.moduleIds,
        )

        for job in blocked_jobs:
            if isinstance(job.metadata_json, dict):
                job.metadata_json = {
                    **job.metadata_json,
                    "moduleStatus": "published",
                }
            self.jobs.update_status(job, status=AIJobStatus.QUEUED)

        self.knowledge.publish_module_sources(module_ids=payload.moduleIds)

        released_job_ids = [job.job_id for job in blocked_jobs]
        self.session.commit()

        for job_id in released_job_ids:
            self._dispatch_job(job_id)

        return ReleaseIndexJobsResponse(
            releasedJobIds=released_job_ids,
            releasedCount=len(released_job_ids),
            dispatchedCount=len(released_job_ids),
        )

    def delete_material_index(self, *, payload: MaterialIndexDeleteRequest) -> MaterialIndexDeleteResponse:
        delete_result = self.knowledge.delete_material_source(material_id=payload.materialId)
        deleted_job_count = self.jobs.delete_by_material_id(material_id=payload.materialId)
        self.session.commit()
        return MaterialIndexDeleteResponse(
            materialId=payload.materialId,
            deletedSourceCount=delete_result.deleted_source_count,
            deletedChunkCount=delete_result.deleted_chunk_count,
            deletedJobCount=deleted_job_count,
        )

    def retry_job(self, *, job_id: int) -> RetryIndexJobResponse:
        job = self.jobs.get_by_id(job_id)
        if job is None:
            raise invalid_request_error("Index job not found")

        if job.status not in {AIJobStatus.FAILED, AIJobStatus.CANCELLED}:
            raise invalid_request_error("Only failed or cancelled jobs can be retried")

        if not isinstance(job.metadata_json, dict):
            job.metadata_json = {}

        job.metadata_json = {
            **job.metadata_json,
            "manualRetryRequested": True,
        }
        self.jobs.update_status(
            job,
            status=AIJobStatus.QUEUED,
            worker_id=None,
            error_message=None,
            next_retry_at=None,
            locked_at=None,
            started_at=None,
            finished_at=None,
        )
        self.session.commit()

        self._dispatch_job(job.job_id)
        return RetryIndexJobResponse(
            jobId=job.job_id,
            status=job.status.value,
            dispatched=True,
        )

    def recover_stale_running_jobs(self) -> RecoverStaleIndexJobsResponse:
        timeout_seconds = max(1, settings.ai_index_job_running_timeout_seconds)
        locked_before = now_local() - timedelta(seconds=timeout_seconds)
        stale_jobs = self.jobs.list_stale_running_jobs(locked_before=locked_before)
        if not stale_jobs:
            return RecoverStaleIndexJobsResponse(
                recoveredJobIds=[],
                recoveredCount=0,
                dispatchedCount=0,
            )

        recovered_job_ids: list[int] = []
        for job in stale_jobs:
            if not isinstance(job.metadata_json, dict):
                job.metadata_json = {}
            job.metadata_json = {
                **job.metadata_json,
                "staleRecoveryRequested": True,
                "staleRecoveredAt": now_local().isoformat(),
            }
            self.jobs.update_status(
                job,
                status=AIJobStatus.QUEUED,
                worker_id=None,
                error_message=job.error_message,
                next_retry_at=None,
                locked_at=None,
                started_at=None,
                finished_at=None,
            )
            recovered_job_ids.append(job.job_id)

        self.session.commit()

        for job_id in recovered_job_ids:
            self._dispatch_job(job_id)

        return RecoverStaleIndexJobsResponse(
            recoveredJobIds=recovered_job_ids,
            recoveredCount=len(recovered_job_ids),
            dispatchedCount=len(recovered_job_ids),
        )

    def _dispatch_job(self, job_id: int) -> None:
        celery_app.send_task(
            "app.tasks.material_index.index_material_task",
            kwargs={"jobId": job_id},
            queue=settings.learning_material_ai_queue,
        )
