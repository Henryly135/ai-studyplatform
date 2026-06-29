from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.ai_index_jobs import AIJobStatus
from app.schemas.index_jobs import MaterialIndexDeleteRequest, MaterialIndexJobRegisterRequest
from app.services.indexing.index_job_service import IndexJobService


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1


class FakeJobsRepository:
    def __init__(self, job=None) -> None:
        self.job = job
        self.superseded = []
        self.updated = []

    def list_replaceable_material_jobs(self, *, material_id):
        return [SimpleNamespace(job_id=1)] if material_id == 99 else []

    def mark_superseded(self, jobs):
        self.superseded.extend(jobs)

    def create_material_job(self, **kwargs):
        status = kwargs.pop("status")
        job = SimpleNamespace(job_id=55, status=status, **kwargs)
        self.job = job
        return job

    def get_by_id(self, job_id):
        return self.job

    def update_status(self, job, *, status, **kwargs):
        job.status = status
        for key, value in kwargs.items():
            setattr(job, key, value)
        self.updated.append((job.job_id, status))
        return job

    def delete_by_material_id(self, *, material_id):
        return 3

    def list_stale_running_jobs(self, *, locked_before):
        return [self.job] if self.job else []


class FakeKnowledgeService:
    def delete_material_source(self, *, material_id):
        return SimpleNamespace(deleted_source_count=1, deleted_chunk_count=2)

    def publish_module_sources(self, *, module_ids):
        return None


def _payload(module_status: str = "published", material_id: int = 88) -> MaterialIndexJobRegisterRequest:
    return MaterialIndexJobRegisterRequest(
        materialId=material_id,
        courseId=1,
        moduleId=2,
        educatorId=7,
        title="Lesson",
        materialType="file",
        resourceUrl="/materials/88",
        storagePath="local://lesson.txt",
        absolutePath="/tmp/lesson.txt",
        contentType="text/plain",
        sizeBytes=10,
        moduleStatus=module_status,
        storageProvider="local",
        storageBucket=None,
        objectKey="lesson.txt",
    )


def test_register_material_job_queues_published_job_and_dispatches(monkeypatch) -> None:
    # Tests published material registration creates queued job and dispatches it.
    session = FakeSession()
    service = IndexJobService(session)
    service.jobs = FakeJobsRepository()
    dispatched = []
    service._dispatch_job = lambda job_id: dispatched.append(job_id)

    result = service.register_material_job(payload=_payload("published", material_id=99))

    assert result.status == "queued"
    assert result.dispatched is True
    assert dispatched == [55]
    assert len(service.jobs.superseded) == 1
    assert session.commit_calls == 1


def test_register_material_job_blocks_draft_job_without_dispatch() -> None:
    # Tests draft material registration creates blocked job without dispatching.
    session = FakeSession()
    service = IndexJobService(session)
    service.jobs = FakeJobsRepository()
    dispatched = []
    service._dispatch_job = lambda job_id: dispatched.append(job_id)

    result = service.register_material_job(payload=_payload("draft"))

    assert result.status == "blocked"
    assert result.dispatched is False
    assert dispatched == []


def test_register_material_job_rejects_unknown_module_status() -> None:
    # Tests material registration validates moduleStatus values.
    service = IndexJobService(FakeSession())
    service.jobs = FakeJobsRepository()

    with pytest.raises(Exception) as exc_info:
        service.register_material_job(payload=_payload("unknown"))

    assert "moduleStatus must be one of" in str(exc_info.value)


def test_delete_material_index_returns_deleted_counts() -> None:
    # Tests material index deletion combines source, chunk, and job delete counts.
    service = IndexJobService(FakeSession())
    service.jobs = FakeJobsRepository()
    service.knowledge = FakeKnowledgeService()

    result = service.delete_material_index(payload=MaterialIndexDeleteRequest(materialId=88))

    assert result.deletedSourceCount == 1
    assert result.deletedChunkCount == 2
    assert result.deletedJobCount == 3


def test_retry_job_requeues_failed_job_and_dispatches() -> None:
    # Tests manual retry requeues failed jobs, updates metadata, and dispatches.
    job = SimpleNamespace(job_id=8, status=AIJobStatus.FAILED, metadata_json=None)
    service = IndexJobService(FakeSession())
    service.jobs = FakeJobsRepository(job)
    dispatched = []
    service._dispatch_job = lambda job_id: dispatched.append(job_id)

    result = service.retry_job(job_id=8)

    assert result.status == "queued"
    assert job.metadata_json["manualRetryRequested"] is True
    assert dispatched == [8]


@pytest.mark.parametrize("job", [None, SimpleNamespace(job_id=9, status=AIJobStatus.SUCCESS, metadata_json={})])
def test_retry_job_rejects_missing_or_non_retryable_jobs(job) -> None:
    # Tests manual retry rejects missing jobs and jobs not failed or cancelled.
    service = IndexJobService(FakeSession())
    service.jobs = FakeJobsRepository(job)

    with pytest.raises(Exception):
        service.retry_job(job_id=9)


def test_recover_stale_running_jobs_requeues_and_dispatches(monkeypatch) -> None:
    # Tests stale running jobs are marked queued with recovery metadata and dispatched.
    job = SimpleNamespace(job_id=10, metadata_json=None, error_message="timeout")
    service = IndexJobService(FakeSession())
    service.jobs = FakeJobsRepository(job)
    dispatched = []
    service._dispatch_job = lambda job_id: dispatched.append(job_id)
    monkeypatch.setattr("app.services.indexing.index_job_service.now_local", lambda: datetime(2026, 4, 29, tzinfo=timezone.utc))
    monkeypatch.setattr(
        "app.services.indexing.index_job_service.settings",
        SimpleNamespace(ai_index_job_running_timeout_seconds=60),
    )

    result = service.recover_stale_running_jobs()

    assert result.recoveredJobIds == [10]
    assert job.metadata_json["staleRecoveryRequested"] is True
    assert dispatched == [10]


def test_recover_stale_running_jobs_returns_empty_when_none_stale(monkeypatch) -> None:
    # Tests stale recovery returns empty counts when no stale jobs exist.
    service = IndexJobService(FakeSession())
    service.jobs = FakeJobsRepository(None)
    monkeypatch.setattr("app.services.indexing.index_job_service.now_local", lambda: datetime(2026, 4, 29, tzinfo=timezone.utc))
    monkeypatch.setattr(
        "app.services.indexing.index_job_service.settings",
        SimpleNamespace(ai_index_job_running_timeout_seconds=60),
    )

    result = service.recover_stale_running_jobs()

    assert result.recoveredCount == 0
    assert result.dispatchedCount == 0
