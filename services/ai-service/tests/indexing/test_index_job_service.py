from __future__ import annotations

from types import SimpleNamespace

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
