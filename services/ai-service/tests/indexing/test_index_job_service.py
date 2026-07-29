from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from app.core.time import now_local
from app.models.ai_index_jobs import AIJobStatus
from app.services.indexing.index_job_service import IndexJobService


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True


class _FakeJobsRepository:
    def __init__(self, jobs: list[SimpleNamespace]) -> None:
        self._jobs = jobs
        self.updated_statuses: list[tuple[int, AIJobStatus]] = []

    def list_blocked_jobs_for_modules(self, *, course_id: int, module_ids: list[int]) -> list[SimpleNamespace]:
        return self._jobs

    def update_status(self, job: SimpleNamespace, *, status: AIJobStatus, **_: object) -> SimpleNamespace:
        job.status = status
        self.updated_statuses.append((job.job_id, status))
        return job


class _FakeKnowledgeService:
    def __init__(self) -> None:
        self.published_module_ids: list[list[int]] = []

    def publish_module_sources(self, *, module_ids: list[int]) -> None:
        self.published_module_ids.append(module_ids)


def test_release_blocked_jobs_updates_metadata_module_status_to_published() -> None:
    # Tests releasing blocked jobs updates metadata, queues jobs, and dispatches them.
    session = _FakeSession()
    blocked_job = SimpleNamespace(
        job_id=101,
        metadata_json={"moduleStatus": "draft", "title": "RL"},
        status=AIJobStatus.BLOCKED,
    )
    jobs = _FakeJobsRepository([blocked_job])
    knowledge = _FakeKnowledgeService()

    service = IndexJobService(session)
    service.jobs = jobs
    service.knowledge = knowledge

    dispatched_job_ids: list[int] = []
    service._dispatch_job = lambda job_id: dispatched_job_ids.append(job_id)

    response = service.release_blocked_jobs(
        payload=SimpleNamespace(courseId=14, moduleIds=[20]),
    )

    assert blocked_job.metadata_json["moduleStatus"] == "published"
    assert blocked_job.status == AIJobStatus.QUEUED
    assert jobs.updated_statuses == [(101, AIJobStatus.QUEUED)]
    assert knowledge.published_module_ids == [[20]]
    assert dispatched_job_ids == [101]
    assert session.committed is True
    assert response.releasedJobIds == [101]
    assert response.releasedCount == 1
    assert response.dispatchedCount == 1


def test_release_blocked_jobs_still_publishes_existing_sources_when_no_jobs() -> None:
    # Tests release still publishes existing sources when no blocked jobs exist.
    session = _FakeSession()
    jobs = _FakeJobsRepository([])
    knowledge = _FakeKnowledgeService()

    service = IndexJobService(session)
    service.jobs = jobs
    service.knowledge = knowledge

    dispatched_job_ids: list[int] = []
    service._dispatch_job = lambda job_id: dispatched_job_ids.append(job_id)

    response = service.release_blocked_jobs(
        payload=SimpleNamespace(courseId=14, moduleIds=[20]),
    )

    assert jobs.updated_statuses == []
    assert knowledge.published_module_ids == [[20]]
    assert dispatched_job_ids == []
    assert session.committed is True
    assert response.releasedJobIds == []
    assert response.releasedCount == 0
    assert response.dispatchedCount == 0


def test_reindex_all_materials_clones_source_metadata_and_dispatches_jobs() -> None:
    session = _FakeSession()
    source = SimpleNamespace(
        source_id=301,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/lesson.pdf",
        content_hash="hash",
        metadata_json={
            "title": "Lesson",
            "materialType": "document",
            "resourceUrl": "/lesson.pdf",
            "storagePath": "materials/lesson.pdf",
            "absolutePath": None,
            "contentType": "application/pdf",
            "sizeBytes": 123,
            "moduleStatus": "published",
            "storageProvider": "minio",
            "storageBucket": "materials",
            "objectKey": "materials/lesson.pdf",
        },
    )
    created_payloads = []
    jobs = SimpleNamespace(
        list_backfill_candidate_material_jobs=lambda: [],
        lock_material_job_scope=lambda **_: None,
        get_latest_backfill_candidate_material_job=lambda **_: None,
        list_replaceable_material_jobs=lambda **_: [],
        create_material_job=lambda **kwargs: (
            created_payloads.append(kwargs)
            or SimpleNamespace(job_id=501)
        ),
    )
    service = IndexJobService(session)
    service.sources = SimpleNamespace(
        list_material_sources=lambda: [source],
        has_material_source_snapshot=lambda **_: True,
    )
    service.jobs = jobs
    dispatched = []
    service._dispatch_job = lambda job_id: dispatched.append(job_id)

    response = service.reindex_all_materials()

    assert created_payloads[0]["status"] == AIJobStatus.QUEUED
    assert created_payloads[0]["metadata_json"]["multiEmbeddingBackfill"] is True
    assert dispatched == [501]
    assert response.jobIds == [501]
    assert response.queuedCount == 1
    assert response.skippedCount == 0


def test_reindex_all_materials_queues_follow_up_from_running_job_snapshot() -> None:
    session = _FakeSession()
    source = SimpleNamespace(
        source_id=302,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="old.pdf",
        content_hash="old-hash",
        metadata_json={"title": "Old"},
    )
    running_metadata = {
        "title": "New Lesson",
        "materialType": "document",
        "resourceUrl": "/new.pdf",
        "storagePath": "materials/new.pdf",
        "contentType": "application/pdf",
        "sizeBytes": 456,
        "moduleStatus": "published",
        "storageProvider": "minio",
        "storageBucket": "materials",
        "objectKey": "materials/new.pdf",
    }
    running_job = SimpleNamespace(
        job_id=700,
        status=AIJobStatus.RUNNING,
        course_id=10,
        module_id=20,
        material_id=3,
        source_version="materials/new.pdf",
        content_hash="new-hash",
        metadata_json=running_metadata,
    )
    created_payloads = []
    jobs = SimpleNamespace(
        list_backfill_candidate_material_jobs=lambda: [running_job],
        lock_material_job_scope=lambda **_: None,
        get_latest_backfill_candidate_material_job=lambda **_: running_job,
        list_replaceable_material_jobs=lambda **_: [],
        create_material_job=lambda **kwargs: (
            created_payloads.append(kwargs)
            or SimpleNamespace(job_id=701)
        ),
    )
    service = IndexJobService(session)
    service.sources = SimpleNamespace(
        list_material_sources=lambda: [source],
        has_material_source_snapshot=lambda **_: True,
    )
    service.jobs = jobs
    dispatched = []
    service._dispatch_job = lambda job_id: dispatched.append(job_id)

    response = service.reindex_all_materials()

    payload = created_payloads[0]
    assert payload["course_id"] == 10
    assert payload["module_id"] == 20
    assert payload["source_version"] == "materials/new.pdf"
    assert payload["content_hash"] == "new-hash"
    assert payload["metadata_json"]["backfillOfJobId"] == 700
    assert dispatched == [701]
    assert response.queuedCount == 1


def test_reindex_all_materials_covers_first_upload_before_source_exists() -> None:
    session = _FakeSession()
    running_metadata = {
        "title": "First Lesson",
        "materialType": "document",
        "resourceUrl": "/first.pdf",
        "storagePath": "materials/first.pdf",
        "contentType": "application/pdf",
        "sizeBytes": 123,
        "moduleStatus": "published",
        "storageProvider": "minio",
        "storageBucket": "materials",
        "objectKey": "materials/first.pdf",
    }
    running_job = SimpleNamespace(
        job_id=800,
        status=AIJobStatus.RUNNING,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/first.pdf",
        content_hash=None,
        metadata_json=running_metadata,
    )
    created_payloads = []
    jobs = SimpleNamespace(
        list_backfill_candidate_material_jobs=lambda: [running_job],
        lock_material_job_scope=lambda **_: None,
        get_latest_backfill_candidate_material_job=lambda **_: running_job,
        list_replaceable_material_jobs=lambda **_: [],
        create_material_job=lambda **kwargs: (
            created_payloads.append(kwargs)
            or SimpleNamespace(job_id=801)
        ),
    )
    service = IndexJobService(session)
    service.sources = SimpleNamespace(list_material_sources=lambda: [])
    service.jobs = jobs
    service._dispatch_job = lambda _job_id: None

    response = service.reindex_all_materials()

    assert response.jobIds == [801]
    assert created_payloads[0]["material_id"] == 3
    assert created_payloads[0]["metadata_json"]["backfillOfJobId"] == 800


def test_reindex_all_materials_never_replaces_newer_queued_upload() -> None:
    session = _FakeSession()
    source = SimpleNamespace(
        source_id=303,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/old.pdf",
        content_hash="old-hash",
        metadata_json={"title": "Old"},
    )
    queued_job = SimpleNamespace(
        job_id=900,
        status=AIJobStatus.QUEUED,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/new.pdf",
        content_hash=None,
        metadata_json={"title": "New"},
    )
    created_payloads = []
    superseded = []
    jobs = SimpleNamespace(
        list_backfill_candidate_material_jobs=lambda: [queued_job],
        lock_material_job_scope=lambda **_: None,
        get_latest_backfill_candidate_material_job=lambda **_: queued_job,
        list_replaceable_material_jobs=lambda **_: [queued_job],
        mark_superseded=lambda rows: superseded.extend(rows),
        create_material_job=lambda **kwargs: created_payloads.append(kwargs),
    )
    service = IndexJobService(session)
    service.sources = SimpleNamespace(
        list_material_sources=lambda: [source],
        has_material_source_snapshot=lambda **_: True,
    )
    service.jobs = jobs
    dispatched = []
    service._dispatch_job = lambda job_id: dispatched.append(job_id)

    response = service.reindex_all_materials()

    assert response.jobIds == [900]
    assert response.queuedCount == 1
    assert response.skippedCount == 0
    assert response.dispatchedCount == 1
    assert dispatched == [900]
    assert created_payloads == []
    assert superseded == []


def test_reindex_all_materials_retries_committed_job_after_broker_recovers() -> None:
    session = _FakeSession()
    source = SimpleNamespace(
        source_id=304,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/lesson.pdf",
        content_hash="hash",
        metadata_json={
            "title": "Lesson",
            "materialType": "document",
            "resourceUrl": "/lesson.pdf",
            "storagePath": "materials/lesson.pdf",
            "contentType": "application/pdf",
            "sizeBytes": 123,
            "moduleStatus": "published",
            "storageProvider": "minio",
            "storageBucket": "materials",
            "objectKey": "materials/lesson.pdf",
        },
    )

    class StatefulJobs:
        def __init__(self) -> None:
            self.created_jobs = []

        def list_backfill_candidate_material_jobs(self):
            return list(reversed(self.created_jobs))

        def lock_material_job_scope(self, **_):
            return None

        def get_latest_backfill_candidate_material_job(self, **_):
            return self.created_jobs[-1] if self.created_jobs else None

        def list_replaceable_material_jobs(self, **_):
            return [
                job
                for job in self.created_jobs
                if job.status
                in {
                    AIJobStatus.BLOCKED,
                    AIJobStatus.QUEUED,
                    AIJobStatus.FAILED,
                }
            ]

        def mark_superseded(self, rows):
            for job in rows:
                job.status = AIJobStatus.SUPERSEDED

        def create_material_job(self, **kwargs):
            job = SimpleNamespace(
                job_id=1001,
                status=kwargs["status"],
                next_retry_at=None,
                course_id=kwargs["course_id"],
                module_id=kwargs["module_id"],
                material_id=kwargs["material_id"],
                source_version=kwargs["source_version"],
                content_hash=kwargs["content_hash"],
                metadata_json=kwargs["metadata_json"],
            )
            self.created_jobs.append(job)
            return job

    jobs = StatefulJobs()
    service = IndexJobService(session)
    service.sources = SimpleNamespace(
        list_material_sources=lambda: [source],
        has_material_source_snapshot=lambda **_: True,
    )
    service.jobs = jobs
    dispatch_attempts = []

    def dispatch_with_first_failure(job_id):
        dispatch_attempts.append(job_id)
        if len(dispatch_attempts) == 1:
            raise RuntimeError("broker unavailable")

    service._dispatch_job = dispatch_with_first_failure

    with pytest.raises(HTTPException) as exc_info:
        service.reindex_all_materials()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "AI_INDEX_DISPATCH_UNAVAILABLE"
    assert len(jobs.created_jobs) == 1
    assert jobs.created_jobs[0].status == AIJobStatus.QUEUED

    response = service.reindex_all_materials()

    assert len(jobs.created_jobs) == 1
    assert dispatch_attempts == [1001, 1001]
    assert response.jobIds == [1001]
    assert response.queuedCount == 1
    assert response.skippedCount == 0
    assert response.dispatchedCount == 1


def test_reindex_all_materials_respects_blocked_and_delayed_retry_jobs() -> None:
    session = _FakeSession()
    blocked_job = SimpleNamespace(
        job_id=1101,
        status=AIJobStatus.BLOCKED,
        material_id=11,
        next_retry_at=None,
    )
    delayed_job = SimpleNamespace(
        job_id=1201,
        status=AIJobStatus.QUEUED,
        material_id=12,
        next_retry_at=now_local() + timedelta(hours=1),
    )
    sources = [
        SimpleNamespace(material_id=11),
        SimpleNamespace(material_id=12),
    ]
    jobs = SimpleNamespace(
        list_backfill_candidate_material_jobs=lambda: [
            delayed_job,
            blocked_job,
        ],
    )
    service = IndexJobService(session)
    service.sources = SimpleNamespace(list_material_sources=lambda: sources)
    service.jobs = jobs
    dispatched = []
    service._dispatch_job = lambda job_id: dispatched.append(job_id)

    response = service.reindex_all_materials()

    assert response.jobIds == []
    assert response.queuedCount == 0
    assert response.skippedCount == 2
    assert response.dispatchedCount == 0
    assert dispatched == []


def test_reindex_all_materials_prefers_newer_successful_source_over_old_running_job() -> None:
    session = _FakeSession()
    source = SimpleNamespace(
        source_id=305,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/new.pdf",
        content_hash="new-hash",
        metadata_json={
            "title": "New",
            "materialType": "document",
            "resourceUrl": "/new.pdf",
            "storagePath": "materials/new.pdf",
            "contentType": "application/pdf",
            "sizeBytes": 456,
            "moduleStatus": "published",
            "storageProvider": "minio",
            "storageBucket": "materials",
            "objectKey": "materials/new.pdf",
        },
    )
    old_running = SimpleNamespace(
        job_id=800,
        status=AIJobStatus.RUNNING,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/old.pdf",
        content_hash="old-hash",
        metadata_json={"title": "Old"},
    )
    newer_success = SimpleNamespace(
        job_id=900,
        status=AIJobStatus.SUCCESS,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/new.pdf",
        content_hash="new-hash",
        metadata_json=source.metadata_json,
    )
    created_payloads = []
    jobs = SimpleNamespace(
        list_backfill_candidate_material_jobs=lambda: [
            newer_success,
            old_running,
        ],
        lock_material_job_scope=lambda **_: None,
        get_latest_backfill_candidate_material_job=lambda **_: newer_success,
        list_replaceable_material_jobs=lambda **_: [],
        create_material_job=lambda **kwargs: (
            created_payloads.append(kwargs)
            or SimpleNamespace(job_id=901)
        ),
    )
    service = IndexJobService(session)
    service.sources = SimpleNamespace(
        list_material_sources=lambda: [source],
        has_material_source_snapshot=lambda **_: True,
    )
    service.jobs = jobs
    service._dispatch_job = lambda _job_id: None

    response = service.reindex_all_materials()

    assert response.queuedCount == 1
    assert created_payloads[0]["source_version"] == "materials/new.pdf"
    assert created_payloads[0]["content_hash"] == "new-hash"
    assert created_payloads[0]["metadata_json"]["backfillOfJobId"] == 900


def test_reindex_all_materials_skips_source_deleted_after_snapshot() -> None:
    session = _FakeSession()
    source = SimpleNamespace(
        source_id=306,
        course_id=1,
        module_id=2,
        material_id=3,
        source_version="materials/deleted.pdf",
        content_hash="deleted-hash",
        metadata_json={
            "title": "Deleted",
            "materialType": "document",
            "resourceUrl": "/deleted.pdf",
            "storagePath": "materials/deleted.pdf",
            "contentType": "application/pdf",
            "sizeBytes": 123,
            "moduleStatus": "published",
            "storageProvider": "minio",
            "storageBucket": "materials",
            "objectKey": "materials/deleted.pdf",
        },
    )
    created_payloads = []
    jobs = SimpleNamespace(
        list_backfill_candidate_material_jobs=lambda: [],
        lock_material_job_scope=lambda **_: None,
        get_latest_backfill_candidate_material_job=lambda **_: None,
        list_replaceable_material_jobs=lambda **_: [],
        create_material_job=lambda **kwargs: created_payloads.append(kwargs),
    )
    service = IndexJobService(session)
    service.sources = SimpleNamespace(
        list_material_sources=lambda: [source],
        has_material_source_snapshot=lambda **_: False,
    )
    service.jobs = jobs
    dispatched = []
    service._dispatch_job = dispatched.append

    response = service.reindex_all_materials()

    assert response.jobIds == []
    assert response.queuedCount == 0
    assert response.skippedCount == 1
    assert response.dispatchedCount == 0
    assert created_payloads == []
    assert dispatched == []
