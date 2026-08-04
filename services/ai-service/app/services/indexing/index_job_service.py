from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.time import now_local
from app.models.ai_index_jobs import AIJobStatus
from app.repositories.ai_index_jobs_repository import AIIndexJobsRepository
from app.repositories.ai_knowledge_sources_repository import AIKnowledgeSourcesRepository
from app.schemas.index_jobs import MaterialIndexDeleteRequest, MaterialIndexDeleteResponse
from app.schemas.index_jobs import (
    MaterialIndexJobRegisterRequest,
    MaterialIndexJobRegisterResponse,
    RecoverStaleIndexJobsResponse,
    ReindexAllMaterialsResponse,
    ReleaseIndexJobsRequest,
    ReleaseIndexJobsResponse,
    RetryIndexJobResponse,
)
from app.services.indexing.knowledge_indexing_service import KnowledgeIndexingService
from platform_common.errors import http_error, invalid_request_error


class IndexJobService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.jobs = AIIndexJobsRepository(session)
        self.knowledge = KnowledgeIndexingService(session)
        self.sources = AIKnowledgeSourcesRepository(session)

    def register_material_job(self, *, payload: MaterialIndexJobRegisterRequest) -> MaterialIndexJobRegisterResponse:
        normalized_module_status = payload.moduleStatus.strip().lower()
        if normalized_module_status not in {"draft", "published", "archived"}:
            raise invalid_request_error("moduleStatus must be one of draft, published, archived")

        self.jobs.lock_material_job_scope(material_id=payload.materialId)
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
        self.jobs.lock_material_job_scope(material_id=payload.materialId)
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
        for stale_snapshot in stale_jobs:
            if stale_snapshot.material_id is None:
                continue
            self.jobs.lock_material_job_scope(
                material_id=stale_snapshot.material_id
            )
            job = self.jobs.get_stale_running_job_for_recovery(
                job_id=stale_snapshot.job_id,
                material_id=stale_snapshot.material_id,
                locked_before=locked_before,
                expected_worker_id=stale_snapshot.worker_id,
                expected_attempt_count=stale_snapshot.attempt_count,
            )
            if job is None:
                # Release the transaction-scoped advisory lock before checking
                # the next snapshot.
                self.session.commit()
                continue
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
            # Commit one material at a time so a slow recovery batch does not
            # hold unrelated material locks.
            self.session.commit()

        for job_id in recovered_job_ids:
            self._dispatch_job(job_id)

        return RecoverStaleIndexJobsResponse(
            recoveredJobIds=recovered_job_ids,
            recoveredCount=len(recovered_job_ids),
            dispatchedCount=len(recovered_job_ids),
        )

    def reindex_all_materials(self) -> ReindexAllMaterialsResponse:
        """Queue a safe multi-vector backfill from canonical source metadata."""

        queued_job_ids: list[int] = []
        skipped_count = 0
        dispatch_ready_at = now_local()
        latest_job_by_material_id = {}
        for candidate_job in self.jobs.list_backfill_candidate_material_jobs():
            if candidate_job.material_id is not None:
                latest_job_by_material_id.setdefault(
                    candidate_job.material_id,
                    candidate_job,
                )

        for source in self.sources.list_material_sources():
            if source.material_id is None:
                skipped_count += 1
                continue
            latest_job = latest_job_by_material_id.pop(
                source.material_id,
                None,
            )
            if latest_job is not None and latest_job.status == AIJobStatus.QUEUED:
                # A not-yet-started job resolves the enabled embedding targets
                # at execution time. Re-publishing its id is safe because the
                # worker claim is atomic, and it recovers a message that was
                # lost after the database commit.
                if self._is_queued_job_ready_for_dispatch(
                    latest_job,
                    ready_at=dispatch_ready_at,
                ):
                    queued_job_ids.append(latest_job.job_id)
                else:
                    skipped_count += 1
                continue
            if latest_job is not None and latest_job.status == AIJobStatus.BLOCKED:
                # A blocked upload must remain behind the module publication
                # gate. release_blocked_jobs is responsible for dispatching it.
                skipped_count += 1
                continue
            snapshot_job = (
                latest_job
                if latest_job is not None
                and latest_job.status in {AIJobStatus.RUNNING, AIJobStatus.FAILED}
                else None
            )
            job = self._create_material_backfill_job(
                material_id=source.material_id,
                course_id=(
                    snapshot_job.course_id
                    if snapshot_job is not None
                    else source.course_id
                ),
                module_id=(
                    snapshot_job.module_id
                    if snapshot_job is not None
                    else source.module_id
                ),
                source_version=(
                    snapshot_job.source_version
                    if snapshot_job is not None
                    else source.source_version
                ),
                content_hash=(
                    snapshot_job.content_hash
                    if snapshot_job is not None
                    else source.content_hash
                ),
                metadata=(
                    snapshot_job.metadata_json
                    if snapshot_job is not None
                    else source.metadata_json
                ),
                snapshot_source_id=(
                    source.source_id if snapshot_job is None else None
                ),
                snapshot_job_id=(
                    snapshot_job.job_id
                    if snapshot_job is not None
                    else latest_job.job_id
                    if latest_job is not None
                    and latest_job.status == AIJobStatus.SUCCESS
                    else None
                ),
            )
            if job is None:
                skipped_count += 1
                continue
            queued_job_ids.append(job.job_id)

        # A first upload may be running or may have failed before a canonical
        # source exists. Clone only that latest authoritative snapshot.
        for latest_job in latest_job_by_material_id.values():
            if latest_job.material_id is None:
                skipped_count += 1
                continue
            if latest_job.status == AIJobStatus.QUEUED:
                if self._is_queued_job_ready_for_dispatch(
                    latest_job,
                    ready_at=dispatch_ready_at,
                ):
                    queued_job_ids.append(latest_job.job_id)
                else:
                    skipped_count += 1
                continue
            if latest_job.status == AIJobStatus.BLOCKED:
                skipped_count += 1
                continue
            if latest_job.status == AIJobStatus.SUCCESS:
                # A successful job must have produced the canonical source.
                # If it is absent, there is no trustworthy snapshot to clone.
                skipped_count += 1
                continue
            job = self._create_material_backfill_job(
                material_id=latest_job.material_id,
                course_id=latest_job.course_id,
                module_id=latest_job.module_id,
                source_version=latest_job.source_version,
                content_hash=latest_job.content_hash,
                metadata=latest_job.metadata_json,
                snapshot_source_id=None,
                snapshot_job_id=latest_job.job_id,
            )
            if job is None:
                skipped_count += 1
                continue
            queued_job_ids.append(job.job_id)

        self.session.commit()
        dispatch_failures: list[tuple[int, Exception]] = []
        for job_id in queued_job_ids:
            try:
                self._dispatch_job(job_id)
            except Exception as exc:
                # Job rows are intentionally committed before publishing so a
                # fast worker cannot race an uncommitted row. Leave failures in
                # QUEUED; the next backfill call republishes those job ids.
                dispatch_failures.append((job_id, exc))

        if dispatch_failures:
            failed_job_ids = [job_id for job_id, _ in dispatch_failures]
            raise http_error(
                status_code=503,
                code="AI_INDEX_DISPATCH_UNAVAILABLE",
                message=(
                    f"{len(failed_job_ids)} index job(s) remain queued because "
                    "message dispatch failed. Retry this operation to dispatch "
                    "the committed jobs."
                ),
            ) from dispatch_failures[0][1]

        return ReindexAllMaterialsResponse(
            jobIds=queued_job_ids,
            queuedCount=len(queued_job_ids),
            skippedCount=skipped_count,
            dispatchedCount=len(queued_job_ids),
        )

    def _create_material_backfill_job(
        self,
        *,
        material_id: int,
        course_id: int | None,
        module_id: int | None,
        source_version: str | None,
        content_hash: str | None,
        metadata: dict | list | None,
        snapshot_source_id: int | None,
        snapshot_job_id: int | None,
    ):
        if (
            not isinstance(metadata, dict)
            or course_id is None
            or module_id is None
        ):
            return None

        required_metadata = {
            "title",
            "materialType",
            "resourceUrl",
            "storagePath",
            "sizeBytes",
            "moduleStatus",
            "storageProvider",
            "objectKey",
        }
        if any(
            metadata.get(key) is None
            or (
                isinstance(metadata.get(key), str)
                and not str(metadata.get(key)).strip()
            )
            for key in required_metadata
        ):
            return None

        self.jobs.lock_material_job_scope(material_id=material_id)
        if (
            snapshot_source_id is not None
            and not self.sources.has_material_source_snapshot(
                source_id=snapshot_source_id,
                material_id=material_id,
                course_id=course_id,
                module_id=module_id,
                source_version=source_version,
                content_hash=content_hash,
            )
        ):
            # The source may have been deleted after the outer backfill scan.
            # Re-check under the material advisory lock so stale snapshots
            # cannot recreate work for a deleted learning material.
            return None

        latest_job = self.jobs.get_latest_backfill_candidate_material_job(
            material_id=material_id
        )
        if snapshot_job_id is not None and (
            latest_job is None
            or latest_job.job_id != snapshot_job_id
            or latest_job.material_id != material_id
            or latest_job.course_id != course_id
            or latest_job.module_id != module_id
            or latest_job.source_version != source_version
            or latest_job.content_hash != content_hash
        ):
            # Physical deletion removes the snapshot row, while replacement
            # uploads change the authoritative id or fingerprint. Either case
            # fences the stale outer scan.
            return None
        if latest_job is not None and (
            snapshot_job_id is None
            or latest_job.status in {AIJobStatus.QUEUED, AIJobStatus.BLOCKED}
        ):
            return None

        replaceable_jobs = self.jobs.list_replaceable_material_jobs(
            material_id=material_id
        )
        if replaceable_jobs:
            self.jobs.mark_superseded(
                [
                    job
                    for job in replaceable_jobs
                    if snapshot_job_id is not None
                    and job.job_id <= snapshot_job_id
                ]
            )

        return self.jobs.create_material_job(
            source_ref_id=str(material_id),
            course_id=course_id,
            module_id=module_id,
            material_id=material_id,
            source_version=source_version,
            content_hash=content_hash,
            metadata_json={
                **metadata,
                "multiEmbeddingBackfill": True,
                **(
                    {"backfillOfJobId": snapshot_job_id}
                    if snapshot_job_id is not None
                    else {}
                ),
            },
            status=AIJobStatus.QUEUED,
            priority=50,
            trigger_event_id=(
                f"material:{material_id}:multi-embedding-backfill"
            ),
        )

    @staticmethod
    def _is_queued_job_ready_for_dispatch(
        job,
        *,
        ready_at,
    ) -> bool:
        next_retry_at = getattr(job, "next_retry_at", None)
        return next_retry_at is None or next_retry_at <= ready_at

    def _dispatch_job(self, job_id: int) -> None:
        celery_app.send_task(
            "app.tasks.material_index.index_material_task",
            kwargs={"jobId": job_id},
            queue=settings.learning_material_ai_queue,
        )
