from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from app.models.ai_index_jobs import AIIndexJob, AIIndexJobType, AIIndexSourceType, AIJobStatus


class AIIndexJobsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, job_id: int) -> AIIndexJob | None:
        return self.session.get(AIIndexJob, job_id)

    def list_replaceable_material_jobs(self, *, material_id: int) -> list[AIIndexJob]:
        stmt = (
            select(AIIndexJob)
            .where(
                AIIndexJob.material_id == material_id,
                AIIndexJob.status.in_(
                    [
                        AIJobStatus.BLOCKED,
                        AIJobStatus.QUEUED,
                        AIJobStatus.FAILED,
                    ]
                ),
            )
            .order_by(AIIndexJob.created_at.desc(), AIIndexJob.job_id.desc())
        )
        return list(self.session.scalars(stmt))

    def delete_by_material_id(self, *, material_id: int) -> int:
        stmt = delete(AIIndexJob).where(AIIndexJob.material_id == material_id)
        result = self.session.execute(stmt)
        self.session.flush()
        return int(result.rowcount or 0)

    def list_blocked_jobs_for_modules(
        self,
        *,
        course_id: int,
        module_ids: Sequence[int],
    ) -> list[AIIndexJob]:
        if not module_ids:
            return []

        stmt = (
            select(AIIndexJob)
            .where(
                AIIndexJob.course_id == course_id,
                AIIndexJob.module_id.in_(list(module_ids)),
                AIIndexJob.status == AIJobStatus.BLOCKED,
            )
            .order_by(AIIndexJob.priority.asc(), AIIndexJob.created_at.asc(), AIIndexJob.job_id.asc())
        )
        return list(self.session.scalars(stmt))

    def list_stale_running_jobs(self, *, locked_before: datetime) -> list[AIIndexJob]:
        stmt = (
            select(AIIndexJob)
            .where(
                AIIndexJob.status == AIJobStatus.RUNNING,
                AIIndexJob.locked_at.is_not(None),
                AIIndexJob.locked_at < locked_before,
            )
            .order_by(AIIndexJob.locked_at.asc(), AIIndexJob.priority.asc(), AIIndexJob.job_id.asc())
        )
        return list(self.session.scalars(stmt))

    def create_material_job(
        self,
        *,
        source_ref_id: str,
        course_id: int,
        module_id: int,
        material_id: int,
        source_version: str | None,
        content_hash: str | None,
        metadata_json: dict | list | None,
        status: AIJobStatus,
        priority: int,
        trigger_event_id: str | None,
    ) -> AIIndexJob:
        job = AIIndexJob(
            job_type=AIIndexJobType.INDEX_MATERIAL,
            source_type=AIIndexSourceType.MATERIAL,
            source_ref_id=source_ref_id,
            course_id=course_id,
            module_id=module_id,
            material_id=material_id,
            source_version=source_version,
            content_hash=content_hash,
            metadata_json=metadata_json,
            status=status,
            priority=priority,
            trigger_event_id=trigger_event_id,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def update_status(
        self,
        job: AIIndexJob,
        *,
        status: AIJobStatus,
        worker_id: str | None = None,
        error_message: str | None = None,
        next_retry_at: datetime | None = None,
        locked_at: datetime | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        attempt_count: int | None = None,
    ) -> AIIndexJob:
        job.status = status
        job.worker_id = worker_id
        job.error_message = error_message
        job.next_retry_at = next_retry_at
        job.locked_at = locked_at
        job.started_at = started_at
        job.finished_at = finished_at
        if attempt_count is not None:
            job.attempt_count = attempt_count
        self.session.flush()
        return job

    def mark_superseded(self, jobs: Sequence[AIIndexJob]) -> None:
        for job in jobs:
            job.status = AIJobStatus.SUPERSEDED
            job.finished_at = None
            job.error_message = None
            job.next_retry_at = None
            job.worker_id = None
            job.locked_at = None
            job.started_at = None
        self.session.flush()
