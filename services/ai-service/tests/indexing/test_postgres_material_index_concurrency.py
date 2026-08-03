from __future__ import annotations

import os
import time
from datetime import timedelta
from queue import Queue
from threading import Thread
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine, create_engine, delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.time import now_local
from app.models.ai_index_jobs import AIIndexJob, AIJobStatus
from app.models.ai_knowledge_chunk_embeddings import AIKnowledgeChunkEmbedding
from app.models.ai_knowledge_chunks import AIKnowledgeChunk
from app.models.ai_knowledge_source_embedding_statuses import (
    AIKnowledgeSourceEmbeddingStatus,
)
from app.models.ai_knowledge_sources import (
    AIKnowledgeSource,
    AIKnowledgeSourceType,
    AIPublishStatus,
    AIVisibilityScope,
)
from app.repositories.ai_index_jobs_repository import AIIndexJobsRepository
from app.schemas.index_jobs import MaterialIndexJobRegisterRequest
from app.services.indexing.index_job_service import IndexJobService
from app.services.indexing.knowledge_indexing_service import KnowledgeIndexingService
from app.tasks.material_index import (
    _MaterialJobLease,
    _acquire_material_write_fence,
)


POSTGRES_TEST_DSN_ENV = "AI_TEST_POSTGRES_DSN"
EMBEDDING_MODEL_ID = "gemini:gemini-embedding-2"
EMBEDDING_VERSION = f"{EMBEDDING_MODEL_ID}@1024"


def _lease_for(job: AIIndexJob) -> _MaterialJobLease:
    return _MaterialJobLease(
        job_id=job.job_id,
        material_id=job.material_id,
        worker_id=str(job.worker_id),
        attempt_count=job.attempt_count,
    )


@pytest.fixture(scope="module")
def postgres_engine() -> Engine:
    dsn = os.getenv(POSTGRES_TEST_DSN_ENV, "").strip()
    if not dsn:
        pytest.skip(
            f"{POSTGRES_TEST_DSN_ENV} is required for PostgreSQL integration tests"
        )

    engine = create_engine(dsn, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            database_name = str(connection.scalar(text("SELECT current_database()")))
            if not database_name.startswith("ai_test_"):
                pytest.skip(
                    "PostgreSQL integration tests require a disposable database "
                    "whose name starts with 'ai_test_'"
                )

            vector_extension = connection.scalar(
                text(
                    "SELECT 1 FROM pg_extension "
                    "WHERE extname = 'vector'"
                )
            )
            required_table_count = int(
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_class "
                        "WHERE relkind = 'r' "
                        "AND relname IN ("
                        "'ai_index_jobs', "
                        "'ai_knowledge_sources', "
                        "'ai_knowledge_chunks', "
                        "'ai_knowledge_chunk_embeddings'"
                        ")"
                    )
                )
                or 0
            )
            existing_test_data = int(
                connection.scalar(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM ai_index_jobs) + "
                        "(SELECT count(*) FROM ai_knowledge_sources)"
                    )
                )
                or 0
            )

        if vector_extension != 1 or required_table_count != 4:
            pytest.skip("PostgreSQL test database has not applied database/ai-init")
        if existing_test_data:
            pytest.skip(
                "PostgreSQL integration tests require an empty disposable database"
            )

        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session_factory(postgres_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=postgres_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@pytest.fixture
def material_id(session_factory: sessionmaker[Session]) -> int:
    value = 8_000_000_000 + (uuid4().int % 900_000_000)
    yield value

    with session_factory() as session:
        session.execute(
            delete(AIIndexJob).where(AIIndexJob.material_id == value)
        )
        session.execute(
            delete(AIKnowledgeSource).where(
                AIKnowledgeSource.material_id == value
            )
        )
        session.commit()


def _material_metadata(material_id: int, *, version: str) -> dict[str, object]:
    object_key = f"postgres-concurrency/{material_id}/{version}.md"
    return {
        "educatorId": 1,
        "title": f"PostgreSQL concurrency material {material_id}",
        "materialType": "text/markdown",
        "resourceUrl": f"/materials/{material_id}",
        "storagePath": object_key,
        "absolutePath": None,
        "contentType": "text/markdown",
        "sizeBytes": 32,
        "moduleStatus": "published",
        "storageProvider": "local",
        "storageBucket": None,
        "objectKey": object_key,
    }


def _create_job(
    session: Session,
    *,
    material_id: int,
    status: AIJobStatus,
    version: str,
) -> AIIndexJob:
    repository = AIIndexJobsRepository(session)
    job = repository.create_material_job(
        source_ref_id=str(material_id),
        course_id=101,
        module_id=201,
        material_id=material_id,
        source_version=str(
            _material_metadata(material_id, version=version)["objectKey"]
        ),
        content_hash=f"content-hash-{version}",
        metadata_json=_material_metadata(material_id, version=version),
        status=status,
        priority=100,
        trigger_event_id=f"material:{material_id}:{version}",
    )
    session.commit()
    return job


def _create_running_job(
    session: Session,
    *,
    material_id: int,
    version: str,
) -> AIIndexJob:
    job = _create_job(
        session,
        material_id=material_id,
        status=AIJobStatus.QUEUED,
        version=version,
    )
    repository = AIIndexJobsRepository(session)
    assert repository.claim_queued_job(
        job_id=job.job_id,
        worker_id="postgres-integration-worker",
        claimed_at=now_local(),
    )
    session.commit()
    return job


def _create_source_graph(
    session: Session,
    *,
    material_id: int,
    version: str,
) -> int:
    metadata = _material_metadata(material_id, version=version)
    source = AIKnowledgeSource(
        source_type=AIKnowledgeSourceType.MATERIAL,
        source_ref_id=str(material_id),
        course_id=101,
        module_id=201,
        material_id=material_id,
        title=str(metadata["title"]),
        content_text=f"source content {version}",
        content_markdown=f"# source content {version}",
        language_code="en",
        visibility_scope=AIVisibilityScope.COURSE_ONLY,
        publish_status=AIPublishStatus.PUBLISHED,
        content_hash=f"content-hash-{version}",
        embedding_model=None,
        embedding_version=None,
        source_version=str(metadata["objectKey"]),
        metadata_json=metadata,
        created_by=1,
        updated_by=1,
        origin_event_id=f"material:{material_id}:{version}",
    )
    session.add(source)
    session.flush()

    chunk = AIKnowledgeChunk(
        source_id=source.source_id,
        course_id=101,
        module_id=201,
        material_id=material_id,
        chunk_index=0,
        chunk_text=f"chunk content {version}",
        token_count=3,
        heading_path=None,
        start_char=0,
        end_char=16,
        chunk_hash=f"chunk-hash-{version}",
        language_code="en",
        visibility_scope=AIVisibilityScope.COURSE_ONLY,
        publish_status=AIPublishStatus.PUBLISHED,
        is_active=True,
        embedding_model=None,
        embedding_version=None,
        embedding=None,
        metadata_json={"title": metadata["title"]},
    )
    session.add(chunk)
    session.flush()

    session.add(
        AIKnowledgeChunkEmbedding(
            chunk_id=chunk.chunk_id,
            embedding_model_id=EMBEDDING_MODEL_ID,
            embedding_version=EMBEDDING_VERSION,
            embedding_dimension=1024,
            embedding=[0.0] * 1024,
        )
    )
    session.add(
        AIKnowledgeSourceEmbeddingStatus(
            source_id=source.source_id,
            embedding_model_id=EMBEDDING_MODEL_ID,
            embedding_version=EMBEDDING_VERSION,
            status="success",
            expected_chunk_count=1,
            indexed_chunk_count=1,
            started_at=now_local(),
            finished_at=now_local(),
        )
    )
    session.commit()
    return source.source_id


def _wait_for_advisory_lock(
    engine: Engine,
    *,
    backend_pid: int,
    timeout_seconds: float = 5.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            wait_state = connection.execute(
                text(
                    "SELECT wait_event_type, wait_event "
                    "FROM pg_stat_activity WHERE pid = :pid"
                ),
                {"pid": backend_pid},
            ).one_or_none()
            if wait_state == ("Lock", "advisory"):
                return
            time.sleep(0.02)
    pytest.fail(f"backend {backend_pid} did not wait for an advisory lock")


def _unwrap_thread_result(
    result_queue: Queue[tuple[str, object]],
) -> object:
    outcome, value = result_queue.get(timeout=10)
    if outcome == "error":
        raise value
    return value


def test_new_upload_supersedes_running_worker_at_postgres_write_fence(
    session_factory: sessionmaker[Session],
    material_id: int,
) -> None:
    with session_factory() as session:
        old_job = _create_running_job(
            session,
            material_id=material_id,
            version="old-upload",
        )
        old_job_id = old_job.job_id

    with session_factory() as session:
        service = IndexJobService(session)
        service._dispatch_job = lambda _job_id: None
        response = service.register_material_job(
            payload=MaterialIndexJobRegisterRequest(
                courseId=101,
                moduleId=201,
                materialId=material_id,
                **_material_metadata(material_id, version="new-upload"),
            )
        )
        new_job_id = response.jobId

    with session_factory() as session:
        repository = AIIndexJobsRepository(session)
        old_job = repository.get_by_id(old_job_id)
        assert old_job is not None
        fence_result = _acquire_material_write_fence(
            session=session,
            jobs=repository,
            lease=_lease_for(old_job),
        )

    assert fence_result is not None
    assert fence_result["status"] == "superseded"

    with session_factory() as session:
        jobs = list(
            session.scalars(
                select(AIIndexJob)
                .where(AIIndexJob.material_id == material_id)
                .order_by(AIIndexJob.job_id)
            )
        )
        assert [job.job_id for job in jobs] == [old_job_id, new_job_id]
        assert [job.status for job in jobs] == [
            AIJobStatus.SUPERSEDED,
            AIJobStatus.QUEUED,
        ]


def test_backfill_triggered_before_worker_commit_gets_final_write_rights(
    postgres_engine: Engine,
    session_factory: sessionmaker[Session],
    material_id: int,
) -> None:
    with session_factory() as seed_session:
        source_id = _create_source_graph(
            seed_session,
            material_id=material_id,
            version="worker-snapshot",
        )
        old_job = _create_running_job(
            seed_session,
            material_id=material_id,
            version="worker-snapshot",
        )
        old_job_id = old_job.job_id

    result_queue: Queue[tuple[str, object]] = Queue()
    pid_queue: Queue[int] = Queue()

    with session_factory() as worker_session:
        worker_jobs = AIIndexJobsRepository(worker_session)
        worker_job = worker_jobs.get_by_id(old_job_id)
        assert worker_job is not None
        assert (
            _acquire_material_write_fence(
                session=worker_session,
                jobs=worker_jobs,
                lease=_lease_for(worker_job),
            )
            is None
        )

        def trigger_backfill() -> None:
            try:
                with session_factory() as backfill_session:
                    backend_pid = int(
                        backfill_session.scalar(select(func.pg_backend_pid()))
                    )
                    pid_queue.put(backend_pid)
                    service = IndexJobService(backfill_session)
                    dispatched_job_ids: list[int] = []
                    service._dispatch_job = dispatched_job_ids.append
                    response = service.reindex_all_materials()
                    result_queue.put(
                        ("ok", (response, dispatched_job_ids))
                    )
            except BaseException as exc:
                result_queue.put(("error", exc))

        backfill_thread = Thread(target=trigger_backfill, daemon=True)
        backfill_thread.start()
        backfill_pid = pid_queue.get(timeout=5)
        _wait_for_advisory_lock(
            postgres_engine,
            backend_pid=backfill_pid,
        )

        source = worker_session.get(AIKnowledgeSource, source_id)
        assert source is not None
        source.content_text = "old worker final write"
        worker_jobs.update_status(
            worker_job,
            status=AIJobStatus.SUCCESS,
            worker_id=worker_job.worker_id,
            locked_at=worker_job.locked_at,
            started_at=worker_job.started_at,
            finished_at=now_local(),
        )
        worker_session.commit()

    backfill_thread.join(timeout=10)
    assert not backfill_thread.is_alive()
    response, dispatched_job_ids = _unwrap_thread_result(result_queue)
    assert response.queuedCount == 1
    assert dispatched_job_ids == response.jobIds
    new_job_id = response.jobIds[0]
    assert new_job_id > old_job_id

    with session_factory() as new_worker_session:
        new_worker_jobs = AIIndexJobsRepository(new_worker_session)
        assert new_worker_jobs.claim_queued_job(
            job_id=new_job_id,
            worker_id="postgres-backfill-worker",
            claimed_at=now_local(),
        )
        new_worker_session.commit()
        new_job = new_worker_jobs.get_by_id(new_job_id)
        assert new_job is not None
        assert (
            _acquire_material_write_fence(
                session=new_worker_session,
                jobs=new_worker_jobs,
                lease=_lease_for(new_job),
            )
            is None
        )
        source = new_worker_session.get(AIKnowledgeSource, source_id)
        assert source is not None
        source.content_text = "new backfill final write"
        new_worker_jobs.update_status(
            new_job,
            status=AIJobStatus.SUCCESS,
            worker_id=new_job.worker_id,
            locked_at=new_job.locked_at,
            started_at=new_job.started_at,
            finished_at=now_local(),
        )
        new_worker_session.commit()

    with session_factory() as stale_worker_session:
        stale_jobs = AIIndexJobsRepository(stale_worker_session)
        stale_job = stale_jobs.get_by_id(old_job_id)
        assert stale_job is not None
        stale_result = _acquire_material_write_fence(
            session=stale_worker_session,
            jobs=stale_jobs,
            lease=_lease_for(stale_job),
        )
        assert stale_result is not None
        assert stale_result["jobStatus"] == "missing_or_not_running"

    with session_factory() as assertion_session:
        source = assertion_session.get(AIKnowledgeSource, source_id)
        assert source is not None
        assert source.content_text == "new backfill final write"
        jobs = list(
            assertion_session.scalars(
                select(AIIndexJob)
                .where(AIIndexJob.material_id == material_id)
                .order_by(AIIndexJob.job_id)
            )
        )
        assert [job.status for job in jobs] == [
            AIJobStatus.SUCCESS,
            AIJobStatus.SUCCESS,
        ]


def test_delete_while_worker_waits_does_not_resurrect_index_rows(
    postgres_engine: Engine,
    session_factory: sessionmaker[Session],
    material_id: int,
) -> None:
    with session_factory() as seed_session:
        _create_source_graph(
            seed_session,
            material_id=material_id,
            version="delete-race",
        )
        job = _create_running_job(
            seed_session,
            material_id=material_id,
            version="delete-race",
        )
        job_id = job.job_id

    result_queue: Queue[tuple[str, object]] = Queue()
    pid_queue: Queue[int] = Queue()

    with session_factory() as delete_session:
        delete_jobs = AIIndexJobsRepository(delete_session)
        delete_jobs.lock_material_job_scope(material_id=material_id)
        delete_result = KnowledgeIndexingService(
            delete_session
        ).delete_material_source(material_id=material_id)
        deleted_job_count = delete_jobs.delete_by_material_id(
            material_id=material_id
        )
        assert delete_result.deleted_source_count == 1
        assert delete_result.deleted_chunk_count == 1
        assert deleted_job_count == 1

        def resume_worker() -> None:
            try:
                with session_factory() as worker_session:
                    worker_job = AIIndexJobsRepository(
                        worker_session
                    ).get_by_id(job_id)
                    assert worker_job is not None
                    backend_pid = int(
                        worker_session.scalar(select(func.pg_backend_pid()))
                    )
                    pid_queue.put(backend_pid)
                    result = _acquire_material_write_fence(
                        session=worker_session,
                        jobs=AIIndexJobsRepository(worker_session),
                        lease=_lease_for(worker_job),
                    )
                    result_queue.put(("ok", result))
            except BaseException as exc:
                result_queue.put(("error", exc))

        worker_thread = Thread(target=resume_worker, daemon=True)
        worker_thread.start()
        worker_pid = pid_queue.get(timeout=5)
        _wait_for_advisory_lock(
            postgres_engine,
            backend_pid=worker_pid,
        )
        delete_session.commit()

    worker_thread.join(timeout=10)
    assert not worker_thread.is_alive()
    worker_result = _unwrap_thread_result(result_queue)
    assert worker_result is not None
    assert worker_result["status"] == "skipped"
    assert worker_result["jobStatus"] == "missing_or_not_running"

    with session_factory() as assertion_session:
        counts = {
            "jobs": assertion_session.scalar(
                select(func.count())
                .select_from(AIIndexJob)
                .where(AIIndexJob.material_id == material_id)
            ),
            "sources": assertion_session.scalar(
                select(func.count())
                .select_from(AIKnowledgeSource)
                .where(AIKnowledgeSource.material_id == material_id)
            ),
            "chunks": assertion_session.scalar(
                select(func.count())
                .select_from(AIKnowledgeChunk)
                .where(AIKnowledgeChunk.material_id == material_id)
            ),
            "vectors": assertion_session.scalar(
                select(func.count())
                .select_from(AIKnowledgeChunkEmbedding)
                .join(
                    AIKnowledgeChunk,
                    AIKnowledgeChunk.chunk_id
                    == AIKnowledgeChunkEmbedding.chunk_id,
                )
                .where(AIKnowledgeChunk.material_id == material_id)
            ),
        }
        assert counts == {
            "jobs": 0,
            "sources": 0,
            "chunks": 0,
            "vectors": 0,
        }


def test_delete_after_backfill_snapshot_does_not_requeue_material(
    postgres_engine: Engine,
    session_factory: sessionmaker[Session],
    material_id: int,
) -> None:
    with session_factory() as seed_session:
        _create_source_graph(
            seed_session,
            material_id=material_id,
            version="delete-backfill-race",
        )
        _create_job(
            seed_session,
            material_id=material_id,
            status=AIJobStatus.SUCCESS,
            version="delete-backfill-race",
        )

    result_queue: Queue[tuple[str, object]] = Queue()
    pid_queue: Queue[int] = Queue()

    with session_factory() as delete_session:
        delete_jobs = AIIndexJobsRepository(delete_session)
        delete_jobs.lock_material_job_scope(material_id=material_id)
        delete_result = KnowledgeIndexingService(
            delete_session
        ).delete_material_source(material_id=material_id)
        deleted_job_count = delete_jobs.delete_by_material_id(
            material_id=material_id
        )
        assert delete_result.deleted_source_count == 1
        assert deleted_job_count == 1

        def trigger_backfill() -> None:
            try:
                with session_factory() as backfill_session:
                    backend_pid = int(
                        backfill_session.scalar(select(func.pg_backend_pid()))
                    )
                    pid_queue.put(backend_pid)
                    service = IndexJobService(backfill_session)
                    dispatched_job_ids: list[int] = []
                    service._dispatch_job = dispatched_job_ids.append
                    response = service.reindex_all_materials()
                    result_queue.put(
                        ("ok", (response, dispatched_job_ids))
                    )
            except BaseException as exc:
                result_queue.put(("error", exc))

        backfill_thread = Thread(target=trigger_backfill, daemon=True)
        backfill_thread.start()
        backfill_pid = pid_queue.get(timeout=5)
        _wait_for_advisory_lock(
            postgres_engine,
            backend_pid=backfill_pid,
        )
        delete_session.commit()

    backfill_thread.join(timeout=10)
    assert not backfill_thread.is_alive()
    response, dispatched_job_ids = _unwrap_thread_result(result_queue)
    assert response.jobIds == []
    assert response.queuedCount == 0
    assert response.skippedCount == 1
    assert response.dispatchedCount == 0
    assert dispatched_job_ids == []

    with session_factory() as assertion_session:
        assert (
            assertion_session.scalar(
                select(func.count())
                .select_from(AIIndexJob)
                .where(AIIndexJob.material_id == material_id)
            )
            == 0
        )
        assert (
            assertion_session.scalar(
                select(func.count())
                .select_from(AIKnowledgeSource)
                .where(AIKnowledgeSource.material_id == material_id)
            )
            == 0
        )


def test_recovered_attempt_fences_old_worker_even_with_same_worker_id(
    session_factory: sessionmaker[Session],
    material_id: int,
) -> None:
    with session_factory() as old_worker_session:
        old_job = _create_running_job(
            old_worker_session,
            material_id=material_id,
            version="stale-lease",
        )
        old_worker_session.refresh(old_job)
        old_job.locked_at = now_local() - timedelta(days=1)
        old_worker_session.commit()
        old_job_id = old_job.job_id
        old_attempt_count = old_job.attempt_count
        old_worker_id = old_job.worker_id
        old_lease = _lease_for(old_job)

        with session_factory() as recovery_session:
            recovery_service = IndexJobService(recovery_session)
            recovery_service._dispatch_job = lambda _job_id: None
            recovery = recovery_service.recover_stale_running_jobs()
        assert recovery.recoveredJobIds == [old_job_id]

        with session_factory() as new_worker_session:
            new_jobs = AIIndexJobsRepository(new_worker_session)
            assert new_jobs.claim_queued_job(
                job_id=old_job_id,
                worker_id=str(old_worker_id),
                claimed_at=now_local(),
            )
            new_worker_session.commit()

        old_worker_session.rollback()
        old_result = _acquire_material_write_fence(
            session=old_worker_session,
            jobs=AIIndexJobsRepository(old_worker_session),
            lease=old_lease,
        )

    assert old_result is not None
    assert old_result["status"] == "skipped"
    with session_factory() as assertion_session:
        current_job = assertion_session.get(AIIndexJob, old_job_id)
        assert current_job is not None
        assert current_job.status == AIJobStatus.RUNNING
        assert current_job.worker_id == old_worker_id
        assert current_job.attempt_count == old_attempt_count + 1


def test_recovery_waits_for_worker_fence_and_skips_committed_success(
    postgres_engine: Engine,
    session_factory: sessionmaker[Session],
    material_id: int,
) -> None:
    with session_factory() as seed_session:
        job = _create_running_job(
            seed_session,
            material_id=material_id,
            version="recovery-fence",
        )
        job.locked_at = now_local() - timedelta(days=1)
        seed_session.commit()
        job_id = job.job_id

    result_queue: Queue[tuple[str, object]] = Queue()
    pid_queue: Queue[int] = Queue()

    with session_factory() as worker_session:
        worker_jobs = AIIndexJobsRepository(worker_session)
        worker_job = worker_jobs.get_by_id(job_id)
        assert worker_job is not None
        worker_jobs.lock_material_job_scope(material_id=material_id)

        def trigger_recovery() -> None:
            try:
                with session_factory() as recovery_session:
                    backend_pid = int(
                        recovery_session.scalar(select(func.pg_backend_pid()))
                    )
                    pid_queue.put(backend_pid)
                    service = IndexJobService(recovery_session)
                    service._dispatch_job = lambda _job_id: None
                    result_queue.put(
                        ("ok", service.recover_stale_running_jobs())
                    )
            except BaseException as exc:
                result_queue.put(("error", exc))

        recovery_thread = Thread(target=trigger_recovery, daemon=True)
        recovery_thread.start()
        recovery_pid = pid_queue.get(timeout=5)
        _wait_for_advisory_lock(
            postgres_engine,
            backend_pid=recovery_pid,
        )

        worker_jobs.update_status(
            worker_job,
            status=AIJobStatus.SUCCESS,
            worker_id=worker_job.worker_id,
            locked_at=worker_job.locked_at,
            started_at=worker_job.started_at,
            finished_at=now_local(),
        )
        worker_session.commit()

    recovery_thread.join(timeout=10)
    assert not recovery_thread.is_alive()
    recovery = _unwrap_thread_result(result_queue)
    assert recovery.recoveredJobIds == []
    assert recovery.recoveredCount == 0
    assert recovery.dispatchedCount == 0

    with session_factory() as assertion_session:
        current_job = assertion_session.get(AIIndexJob, job_id)
        assert current_job is not None
        assert current_job.status == AIJobStatus.SUCCESS


def test_dispatch_failure_leaves_one_republishable_queued_job(
    session_factory: sessionmaker[Session],
    material_id: int,
) -> None:
    with session_factory() as seed_session:
        _create_source_graph(
            seed_session,
            material_id=material_id,
            version="dispatch-retry",
        )
        original_job = _create_job(
            seed_session,
            material_id=material_id,
            status=AIJobStatus.SUCCESS,
            version="dispatch-retry",
        )
        original_job_id = original_job.job_id

    with session_factory() as first_session:
        first_service = IndexJobService(first_session)

        def fail_dispatch(_job_id: int) -> None:
            raise RuntimeError("synthetic broker outage")

        first_service._dispatch_job = fail_dispatch
        with pytest.raises(HTTPException) as exc_info:
            first_service.reindex_all_materials()
        assert exc_info.value.status_code == 503

    with session_factory() as assertion_session:
        queued_jobs = list(
            assertion_session.scalars(
                select(AIIndexJob)
                .where(
                    AIIndexJob.material_id == material_id,
                    AIIndexJob.status == AIJobStatus.QUEUED,
                )
                .order_by(AIIndexJob.job_id)
            )
        )
        assert len(queued_jobs) == 1
        queued_job_id = queued_jobs[0].job_id
        assert queued_job_id > original_job_id

    with session_factory() as retry_session:
        retry_service = IndexJobService(retry_session)
        dispatched_job_ids: list[int] = []
        retry_service._dispatch_job = dispatched_job_ids.append
        retry_response = retry_service.reindex_all_materials()

    assert retry_response.jobIds == [queued_job_id]
    assert dispatched_job_ids == [queued_job_id]
    with session_factory() as final_session:
        jobs = list(
            final_session.scalars(
                select(AIIndexJob)
                .where(AIIndexJob.material_id == material_id)
                .order_by(AIIndexJob.job_id)
            )
        )
        assert [job.job_id for job in jobs] == [
            original_job_id,
            queued_job_id,
        ]
        assert [job.status for job in jobs] == [
            AIJobStatus.SUCCESS,
            AIJobStatus.QUEUED,
        ]
