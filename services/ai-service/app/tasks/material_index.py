from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.time import now_local
from app.db.session import SessionLocal
from app.models.ai_index_jobs import AIJobStatus
from app.models.ai_knowledge_chunk_embeddings import MULTI_EMBEDDING_DIMENSION
from app.models.ai_knowledge_chunks import AIKnowledgeChunk
from app.models.ai_knowledge_sources import (
    AIKnowledgeSource,
    AIPublishStatus,
    AIKnowledgeSourceType,
    AIVisibilityScope,
)
from app.models.ai_prompt_logs import AIPromptStatus
from app.repositories.ai_embedding_logs_repository import AIEmbeddingLogsRepository
from app.repositories.ai_index_jobs_repository import AIIndexJobsRepository
from app.repositories.ai_knowledge_chunks_repository import ChunkCreate
from app.services.indexing.embedding_service import EmbeddingService
from app.services.indexing.knowledge_indexing_service import (
    KnowledgeIndexingResult,
    KnowledgeIndexingService,
    SourceUpsert,
)
from app.services.indexing.material_content_service import MaterialContentRequest, MaterialContentService
from app.services.indexing.text_chunking_service import TextChunkingService
from platform_common.errors import invalid_request_error


@dataclass(frozen=True)
class _MaterialJobLease:
    job_id: int
    material_id: int | None
    worker_id: str
    attempt_count: int


def _safe_task_error_message(*, stage: str, exc: Exception) -> str:
    return f"[{stage}] {type(exc).__name__}"


@celery_app.task(bind=True, name="app.tasks.material_index.index_material_task")
def index_material_task(self, jobId: int) -> dict[str, object]:
    '''Celery task to process material indexing jobs.'''
    session: Session = SessionLocal()
    jobs = AIIndexJobsRepository(session)
    current_time = now_local()

    # Stage is for error tracking in case of exceptions
    # Stage 1: Initialization
    stage = "initializing"
    embedding_logs = AIEmbeddingLogsRepository(session)
    claimed_lease: _MaterialJobLease | None = None

    try:
        # Stage 2: Job Retrieval and Validation
        stage = "loading_job"
        job = jobs.get_by_id(jobId)
        if job is None:
            raise ValueError(f"AI index job {jobId} not found")

        if job.status == AIJobStatus.SUCCESS:
            return {
                "status": "already_processed",
                "jobId": job.job_id,
                "courseId": job.course_id,
                "moduleId": job.module_id,
                "materialId": job.material_id,
            }

        if job.status != AIJobStatus.QUEUED:
            return {
                "status": "skipped",
                "jobId": job.job_id,
                "jobStatus": job.status.value,
            }

        worker_id = str(
            getattr(self.request, "id", "")
            or getattr(self.request, "hostname", "")
            or "ai-worker"
        )
        if not jobs.claim_queued_job(
            job_id=job.job_id,
            worker_id=worker_id,
            claimed_at=current_time,
        ):
            session.rollback()
            current_job = jobs.get_by_id(jobId)
            return {
                "status": "skipped",
                "jobId": jobId,
                "jobStatus": (
                    current_job.status.value
                    if current_job is not None
                    else "missing"
                ),
            }
        session.commit()
        session.refresh(job)
        claimed_lease = _MaterialJobLease(
            job_id=job.job_id,
            material_id=job.material_id,
            worker_id=str(job.worker_id),
            attempt_count=job.attempt_count,
        )

        content_service = MaterialContentService(session)
        chunking_service = TextChunkingService()
        embedding_service = EmbeddingService(session)
        indexing_service = KnowledgeIndexingService(session)

        # Stage 3: Metadata Validation and Content Extraction
        stage = "metadata_validation"
        metadata = _get_material_job_metadata(job.metadata_json)

        # Stage 4: Content Extraction from uploaded materials
        stage = "content_extraction"
        extracted = content_service.extract_text(
            request=MaterialContentRequest(
                title=str(metadata["title"]),
                content_type=_optional_str(metadata.get("contentType")),
                storage_provider=str(metadata["storageProvider"]),
                absolute_path=_optional_str(metadata.get("absolutePath")),
                storage_bucket=_optional_str(metadata.get("storageBucket")),
                object_key=str(metadata["objectKey"]),
            )
        )
        content_hash = sha256(extracted.content_text.encode("utf-8")).hexdigest()

        # Stage 5: Text Chunking, Embedding, and Indexing
        stage = "chunking"
        text_chunks = chunking_service.chunk_text(content_text=extracted.content_text)
        publish_status = _to_publish_status(str(metadata["moduleStatus"]))
        source_metadata = {
            "educatorId": metadata.get("educatorId"),
            "title": metadata["title"],
            "materialType": metadata["materialType"],
            "resourceUrl": metadata["resourceUrl"],
            "storagePath": metadata["storagePath"],
            "absolutePath": metadata.get("absolutePath"),
            "contentType": metadata.get("contentType"),
            "sizeBytes": metadata["sizeBytes"],
            "moduleStatus": metadata["moduleStatus"],
            "storageProvider": metadata["storageProvider"],
            "storageBucket": metadata.get("storageBucket"),
            "objectKey": metadata["objectKey"],
            "chunkCount": len(text_chunks),
        }

        # Stage 6: Persist provider-independent canonical chunks first.
        chunk_rows: list[ChunkCreate] = []
        for text_chunk in text_chunks:
            chunk_rows.append(
                ChunkCreate(
                    source_id=0,
                    course_id=job.course_id,
                    module_id=job.module_id,
                    material_id=job.material_id,
                    chunk_index=text_chunk.chunk_index,
                    chunk_text=text_chunk.chunk_text,
                    token_count=None,
                    heading_path=None,
                    start_char=text_chunk.start_char,
                    end_char=text_chunk.end_char,
                    chunk_hash=text_chunk.chunk_hash,
                    language_code=None,
                    visibility_scope=AIVisibilityScope.COURSE_ONLY,
                    publish_status=publish_status,
                    is_active=True,
                    metadata_json={
                        "title": metadata["title"],
                        "objectKey": metadata["objectKey"],
                        "contentType": metadata.get("contentType"),
                    },
                )
            )


        # Stage 7: Generate all provider vectors before replacing the current
        # index. Existing RAG data remains visible until at least one complete
        # replacement vector set is ready.
        existing_source = indexing_service.sources.get_by_type_and_ref(
            source_type=AIKnowledgeSourceType.MATERIAL,
            source_ref_id=str(job.material_id),
        )
        existing_chunks = (
            indexing_service.chunks.list_by_source_id(existing_source.source_id)
            if existing_source is not None
            else []
        )
        expected_chunk_fingerprint = [
            (chunk.chunk_index, chunk.chunk_hash)
            for chunk in text_chunks
        ]
        existing_chunk_fingerprint = [
            (chunk.chunk_index, chunk.chunk_hash)
            for chunk in existing_chunks
        ]
        can_reuse_canonical_chunks = _can_reuse_canonical_chunks(
            source=existing_source,
            chunks=existing_chunks,
            content_hash=content_hash,
            source_version=str(metadata["objectKey"]),
            publish_status=publish_status,
            existing_chunk_fingerprint=existing_chunk_fingerprint,
            expected_chunk_fingerprint=expected_chunk_fingerprint,
        )
        embedding_targets = embedding_service.list_available_embedding_models()
        if not embedding_targets:
            superseded_response = _acquire_material_write_fence(
                session=session,
                jobs=jobs,
                lease=claimed_lease,
            )
            if superseded_response is not None:
                return superseded_response
            job.content_hash = content_hash
            if existing_source is not None and not can_reuse_canonical_chunks:
                indexing_service.mark_source_index_stale(
                    source=existing_source,
                    pending_content_hash=content_hash,
                    pending_source_version=str(metadata["objectKey"]),
                )
            session.commit()
            stage = "embedding_model_configuration"
            raise invalid_request_error("No configured embedding model is available")

        target_by_model_id = {
            target.model_id: target for target in embedding_targets
        }
        existing_successful_models: set[str] = set()
        if can_reuse_canonical_chunks and existing_source is not None:
            for embedding_status in indexing_service.embedding_statuses.list_by_source_id(
                existing_source.source_id
            ):
                target = target_by_model_id.get(
                    embedding_status.embedding_model_id
                )
                if (
                    target is not None
                    and embedding_status.status == "success"
                    and embedding_status.embedding_version
                    == target.embedding_version
                    and embedding_status.expected_chunk_count == len(text_chunks)
                    and embedding_status.indexed_chunk_count == len(text_chunks)
                ):
                    existing_successful_models.add(target.model_id)
        pending_embedding_targets = [
            target
            for target in embedding_targets
            if target.model_id not in existing_successful_models
        ]

        prompt_log_user_id = _get_prompt_log_user_id(metadata)
        successful_embedding_models: list[str] = sorted(
            existing_successful_models
        )
        failed_embedding_models: list[dict[str, str]] = []
        successful_executions = []
        failed_attempts = []
        first_embedding_error: Exception | None = None

        for target in pending_embedding_targets:
            stage = f"embedding_model_{target.model_id}"
            executions = []
            failed_chunk = None
            failed_token_count = None
            try:
                for text_chunk in text_chunks:
                    failed_chunk = text_chunk
                    failed_token_count = embedding_service.count_document_tokens(
                        text=text_chunk.chunk_text,
                        embedding_model_id=target.model_id,
                    )
                    embedding_result = embedding_service.embed_document(
                        text=text_chunk.chunk_text,
                        title=str(metadata["title"]),
                        embedding_model_id=target.model_id,
                    )
                    executions.append(
                        (text_chunk, failed_token_count, embedding_result)
                    )
                successful_embedding_models.append(target.model_id)
                successful_executions.append((target, executions))
            except Exception as exc:
                if first_embedding_error is None:
                    first_embedding_error = exc
                error_message = _safe_task_error_message(stage=stage, exc=exc)
                failed_attempts.append(
                    (target, failed_chunk, failed_token_count, error_message)
                )
                failed_embedding_models.append(
                    {
                        "modelId": target.model_id,
                        "error": error_message,
                    }
                )

        if not successful_embedding_models:
            superseded_response = _acquire_material_write_fence(
                session=session,
                jobs=jobs,
                lease=claimed_lease,
            )
            if superseded_response is not None:
                return superseded_response
            job.content_hash = content_hash
            if existing_source is not None:
                if not can_reuse_canonical_chunks:
                    indexing_service.mark_source_index_stale(
                        source=existing_source,
                        pending_content_hash=content_hash,
                        pending_source_version=str(metadata["objectKey"]),
                    )
                for target, _, _, error_message in failed_attempts:
                    indexing_service.mark_embedding_index_failed(
                        source_id=existing_source.source_id,
                        embedding_model_id=target.model_id,
                        embedding_version=target.embedding_version,
                        expected_chunk_count=len(text_chunks),
                        indexed_chunk_count=0,
                        last_error=error_message,
                    )
            for target, failed_chunk, failed_token_count, error_message in failed_attempts:
                if failed_chunk is None:
                    continue
                embedding_logs.create(
                    job_id=job.job_id,
                    user_id=prompt_log_user_id,
                    course_id=job.course_id,
                    module_id=job.module_id,
                    material_id=job.material_id,
                    chunk_index=failed_chunk.chunk_index,
                    chunk_hash=failed_chunk.chunk_hash,
                    model_name=target.model_id,
                    model_version=target.embedding_version,
                    task_type=settings.ai_embedding_task_type,
                    title=str(metadata["title"]),
                    input_text=_truncate_text(failed_chunk.chunk_text),
                    input_chars=len(failed_chunk.chunk_text),
                    provider_input_tokens=(
                        failed_token_count.provider_input_tokens
                        if failed_token_count is not None
                        else None
                    ),
                    provider_total_tokens=(
                        failed_token_count.provider_total_tokens
                        if failed_token_count is not None
                        else None
                    ),
                    vector_length=None,
                    output_dimensionality=target.dimension,
                    request_json={"embeddingModelId": target.model_id},
                    response_json=None,
                    latency_ms=None,
                    status=AIPromptStatus.FAILED,
                    error_message=error_message,
                    trace_id=None,
                )
            superseded_response = _supersede_if_newer_material_job(
                session=session,
                jobs=jobs,
                lease=claimed_lease,
            )
            if superseded_response is not None:
                return superseded_response
            session.commit()
            if first_embedding_error is not None:
                raise first_embedding_error
            raise invalid_request_error("No embedding model completed indexing")

        superseded_response = _acquire_material_write_fence(
            session=session,
            jobs=jobs,
            lease=claimed_lease,
        )
        if superseded_response is not None:
            return superseded_response
        job.content_hash = content_hash

        # Stage 8: Atomically swap canonical chunks and every complete vector
        # set, then expose provider-specific readiness in the same commit.
        stage = "multi_vector_index_write"
        source_data = SourceUpsert(
                source_type=AIKnowledgeSourceType.MATERIAL,
                source_ref_id=str(job.material_id),
                course_id=job.course_id,
                module_id=job.module_id,
                material_id=job.material_id,
                title=str(metadata["title"]),
                content_text=extracted.content_text,
                content_markdown=_to_markdown_content(
                    content_text=extracted.content_text,
                    content_type=_optional_str(metadata.get("contentType")),
                    object_key=str(metadata["objectKey"]),
                ),
                language_code=None,
                visibility_scope=AIVisibilityScope.COURSE_ONLY,
                publish_status=publish_status,
                content_hash=content_hash,
                embedding_model=None,
                embedding_version=None,
                source_version=str(metadata["objectKey"]),
                metadata_json=source_metadata,
                created_by=None,
                updated_by=None,
                origin_event_id=job.trigger_event_id,
        )
        if can_reuse_canonical_chunks and existing_source is not None:
            indexing_result = KnowledgeIndexingResult(
                source=existing_source,
                source_created=False,
                deleted_chunk_count=0,
                chunk_count=len(existing_chunks),
                created_chunks=existing_chunks,
            )
        else:
            indexing_result = indexing_service.replace_source_chunks(
                source_data=source_data,
                chunks=chunk_rows,
            )

        for target, executions in successful_executions:
            indexing_service.mark_embedding_index_running(
                source_id=indexing_result.source.source_id,
                embedding_model_id=target.model_id,
                embedding_version=target.embedding_version,
                expected_chunk_count=len(text_chunks),
            )
            indexing_service.write_source_embeddings(
                source_id=indexing_result.source.source_id,
                embedding_model_id=target.model_id,
                embedding_version=target.embedding_version,
                embeddings_by_chunk_index={
                    text_chunk.chunk_index: embedding_result.vector
                    for text_chunk, _, embedding_result in executions
                },
            )
            for text_chunk, token_count, embedding_result in executions:
                embedding_logs.create(
                    job_id=job.job_id,
                    user_id=prompt_log_user_id,
                    course_id=job.course_id,
                    module_id=job.module_id,
                    material_id=job.material_id,
                    chunk_index=text_chunk.chunk_index,
                    chunk_hash=text_chunk.chunk_hash,
                    model_name=embedding_result.embedding_model_id,
                    model_version=embedding_result.embedding_version,
                    task_type=embedding_result.task_type,
                    title=str(metadata["title"]),
                    input_text=_truncate_text(text_chunk.chunk_text),
                    input_chars=len(text_chunk.chunk_text),
                    provider_input_tokens=(
                        embedding_result.provider_input_tokens
                        if embedding_result.provider_input_tokens is not None
                        else token_count.provider_input_tokens
                    ),
                    provider_total_tokens=(
                        embedding_result.provider_total_tokens
                        if embedding_result.provider_total_tokens is not None
                        else token_count.provider_total_tokens
                    ),
                    vector_length=len(embedding_result.vector),
                    output_dimensionality=embedding_result.output_dimensionality,
                    request_json={
                        "tokenCount": token_count.request_json,
                        "embedding": embedding_result.request_json,
                    },
                    response_json={
                        "tokenCount": token_count.response_json,
                        "embedding": embedding_result.response_json,
                    },
                    latency_ms=embedding_result.latency_ms,
                    status=embedding_result.status,
                    error_message=embedding_result.error_message,
                    trace_id=embedding_result.trace_id,
                )

        for target, failed_chunk, failed_token_count, error_message in failed_attempts:
            indexing_service.mark_embedding_index_failed(
                source_id=indexing_result.source.source_id,
                embedding_model_id=target.model_id,
                embedding_version=target.embedding_version,
                expected_chunk_count=len(text_chunks),
                indexed_chunk_count=0,
                last_error=error_message,
            )
            if failed_chunk is not None:
                embedding_logs.create(
                    job_id=job.job_id,
                    user_id=prompt_log_user_id,
                    course_id=job.course_id,
                    module_id=job.module_id,
                    material_id=job.material_id,
                    chunk_index=failed_chunk.chunk_index,
                    chunk_hash=failed_chunk.chunk_hash,
                    model_name=target.model_id,
                    model_version=target.embedding_version,
                    task_type=settings.ai_embedding_task_type,
                    title=str(metadata["title"]),
                    input_text=_truncate_text(failed_chunk.chunk_text),
                    input_chars=len(failed_chunk.chunk_text),
                    provider_input_tokens=(
                        failed_token_count.provider_input_tokens
                        if failed_token_count is not None
                        else None
                    ),
                    provider_total_tokens=(
                        failed_token_count.provider_total_tokens
                        if failed_token_count is not None
                        else None
                    ),
                    vector_length=None,
                    output_dimensionality=target.dimension,
                    request_json={
                        "embeddingModelId": target.model_id,
                        "contentsPreview": failed_chunk.chunk_text[:500],
                    },
                    response_json=None,
                    latency_ms=None,
                    status=AIPromptStatus.FAILED,
                    error_message=error_message,
                    trace_id=None,
                )

        superseded_response = _supersede_if_newer_material_job(
            session=session,
            jobs=jobs,
            lease=claimed_lease,
        )
        if superseded_response is not None:
            return superseded_response

        processed_at = now_local()
        if not isinstance(job.metadata_json, dict):
            job.metadata_json = {}
        job.metadata_json = {
            **job.metadata_json,
            "indexedEmbeddingModels": successful_embedding_models,
            "failedEmbeddingModels": failed_embedding_models,
            "multiEmbeddingDimension": MULTI_EMBEDDING_DIMENSION,
        }
        if failed_embedding_models:
            # Keep complete provider vectors available, but leave the job in
            # the standard retry path until every configured pair is covered.
            superseded_response = _supersede_if_newer_material_job(
                session=session,
                jobs=jobs,
                lease=claimed_lease,
            )
            if superseded_response is not None:
                return superseded_response
            session.commit()
            stage = "embedding_partial"
            raise RuntimeError(
                "One or more embedding providers failed; partial vectors remain available"
            )
        jobs.update_status(
            job,
            status=AIJobStatus.SUCCESS,
            worker_id=job.worker_id,
            next_retry_at=None,
            locked_at=job.locked_at,
            started_at=job.started_at,
            finished_at=processed_at,
        )
        superseded_response = _supersede_if_newer_material_job(
            session=session,
            jobs=jobs,
            lease=claimed_lease,
        )
        if superseded_response is not None:
            return superseded_response
        session.commit()

        return {
            "status": "accepted",
            "jobId": job.job_id,
            "jobType": job.job_type.value,
            "courseId": job.course_id,
            "moduleId": job.module_id,
            "materialId": job.material_id,
            "title": metadata["title"],
            "contentType": metadata["contentType"],
            "storageProvider": metadata["storageProvider"],
            "objectKey": metadata["objectKey"],
            "contentHash": content_hash,
            "extractedTextLength": len(extracted.content_text),
            "sourceId": indexing_result.source.source_id,
            "sourceCreated": indexing_result.source_created,
            "deletedChunkCount": indexing_result.deleted_chunk_count,
            "chunkCount": indexing_result.chunk_count,
            "embeddingModels": successful_embedding_models,
            "embeddingFailures": failed_embedding_models,
            "processedAt": processed_at.isoformat(timespec="seconds"),
        }
    
    except Exception as exc:
        session.rollback()
        if claimed_lease is not None:
            fence_response = _acquire_material_write_fence(
                session=session,
                jobs=jobs,
                lease=claimed_lease,
            )
            if fence_response is not None:
                return fence_response
            if claimed_lease.material_id is None:
                return _missing_material_job_response(claimed_lease)
            job = jobs.get_running_material_job_for_lease(
                job_id=claimed_lease.job_id,
                material_id=claimed_lease.material_id,
                expected_worker_id=claimed_lease.worker_id,
                expected_attempt_count=claimed_lease.attempt_count,
            )
            if job is None:
                session.rollback()
                return _missing_or_changed_lease_response(claimed_lease)
        else:
            job = jobs.get_by_id(jobId)
        if job is not None:
            if not isinstance(job.metadata_json, dict):
                job.metadata_json = {}
            current_attempt = job.attempt_count or 0
            error_message = _safe_task_error_message(stage=stage, exc=exc)
            if _should_auto_retry(exc=exc, stage=stage) and current_attempt < settings.ai_index_job_max_auto_retries:
                retry_delay_seconds = _compute_retry_delay_seconds(current_attempt)
                retry_at = now_local() + timedelta(seconds=retry_delay_seconds)
                job.metadata_json = {
                    **job.metadata_json,
                    "lastErrorStage": stage,
                    "lastErrorType": type(exc).__name__,
                    "lastErrorMessage": error_message,
                    "autoRetryScheduledAt": retry_at.isoformat(),
                    "autoRetryDelaySeconds": retry_delay_seconds,
                    "autoRetryAttempt": current_attempt + 1,
                }
                jobs.update_status(
                    job,
                    status=AIJobStatus.QUEUED,
                    worker_id=None,
                    locked_at=None,
                    started_at=None,
                    finished_at=None,
                    next_retry_at=retry_at,
                    error_message=error_message,
                )
                session.commit()
                try:
                    celery_app.send_task(
                        "app.tasks.material_index.index_material_task",
                        kwargs={"jobId": job.job_id},
                        queue=settings.learning_material_ai_queue,
                        countdown=retry_delay_seconds,
                    )
                except Exception as dispatch_exc:
                    session.rollback()
                    retry_job = jobs.get_by_id(jobId)
                    if retry_job is not None:
                        if not isinstance(retry_job.metadata_json, dict):
                            retry_job.metadata_json = {}
                        retry_job.metadata_json = {
                            **retry_job.metadata_json,
                            "retryDispatchErrorType": type(dispatch_exc).__name__,
                            "retryDispatchErrorMessage": _safe_task_error_message(
                                stage="retry_dispatch",
                                exc=dispatch_exc,
                            ),
                        }
                        jobs.update_status(
                            retry_job,
                            status=AIJobStatus.FAILED,
                            worker_id=retry_job.worker_id,
                            locked_at=retry_job.locked_at,
                            started_at=retry_job.started_at,
                            finished_at=now_local(),
                            next_retry_at=None,
                            error_message=_safe_task_error_message(stage="retry_dispatch", exc=dispatch_exc),
                        )
                        session.commit()
                    raise
                return {
                    "status": "retry_scheduled",
                    "jobId": job.job_id,
                    "materialId": job.material_id,
                    "attemptCount": current_attempt,
                    "nextRetryAt": retry_at.isoformat(timespec="seconds"),
                    "retryDelaySeconds": retry_delay_seconds,
                }

            job.metadata_json = {
                **job.metadata_json,
                "lastErrorStage": stage,
                "lastErrorType": type(exc).__name__,
                "lastErrorMessage": error_message,
            }
            jobs.update_status(
                job,
                status=AIJobStatus.FAILED,
                worker_id=job.worker_id,
                locked_at=job.locked_at,
                started_at=job.started_at,
                finished_at=now_local(),
                next_retry_at=None,
                error_message=error_message,
            )
            session.commit()
        raise
    
    finally:
        session.close()


def _acquire_material_write_fence(
    *,
    session: Session,
    jobs: AIIndexJobsRepository,
    lease: _MaterialJobLease,
) -> dict[str, object] | None:
    """Linearize final index writes against register/backfill/delete."""

    job_id = lease.job_id
    material_id = lease.material_id
    if material_id is None:
        session.rollback()
        return _missing_material_job_response(lease)

    jobs.lock_material_job_scope(material_id=material_id)
    current_job = jobs.get_running_material_job_for_lease(
        job_id=job_id,
        material_id=material_id,
        expected_worker_id=lease.worker_id,
        expected_attempt_count=lease.attempt_count,
    )
    if current_job is None:
        # The row may have been deleted while this worker waited for the lock.
        # Do not consult the possibly stale ORM identity after the rollback.
        session.rollback()
        return _missing_or_changed_lease_response(lease)

    return _supersede_if_newer_material_job(
        session=session,
        jobs=jobs,
        lease=lease,
    )


def _supersede_if_newer_material_job(
    *,
    session: Session,
    jobs: AIIndexJobsRepository,
    lease: _MaterialJobLease,
) -> dict[str, object] | None:
    material_id = lease.material_id
    job_id = lease.job_id
    if material_id is None or not jobs.has_newer_material_job(
        material_id=material_id,
        job_id=job_id,
    ):
        return None

    # Discard every pending source/vector/status mutation from the older job,
    # then persist only its terminal superseded state.
    session.rollback()
    jobs.lock_material_job_scope(material_id=material_id)
    current_job = jobs.get_running_material_job_for_lease(
        job_id=job_id,
        material_id=material_id,
        expected_worker_id=lease.worker_id,
        expected_attempt_count=lease.attempt_count,
    )
    if current_job is None:
        session.rollback()
        return _missing_or_changed_lease_response(lease)
    superseded_at = now_local()
    jobs.update_status(
        current_job,
        status=AIJobStatus.SUPERSEDED,
        worker_id=None,
        next_retry_at=None,
        locked_at=None,
        started_at=current_job.started_at,
        finished_at=superseded_at,
        error_message=None,
    )
    session.commit()

    return {
        "status": "superseded",
        "jobId": job_id,
        "materialId": material_id,
        "processedAt": superseded_at.isoformat(timespec="seconds"),
    }


def _missing_material_job_response(
    lease: _MaterialJobLease,
) -> dict[str, object]:
    return {
        "status": "skipped",
        "jobId": lease.job_id,
        "materialId": None,
        "jobStatus": "missing_material",
    }


def _missing_or_changed_lease_response(
    lease: _MaterialJobLease,
) -> dict[str, object]:
    return {
        "status": "skipped",
        "jobId": lease.job_id,
        "materialId": lease.material_id,
        "jobStatus": "missing_or_not_running",
    }


def _can_reuse_canonical_chunks(
    *,
    source: AIKnowledgeSource | None,
    chunks: list[AIKnowledgeChunk],
    content_hash: str,
    source_version: str,
    publish_status: AIPublishStatus,
    existing_chunk_fingerprint: list[tuple[int, str]],
    expected_chunk_fingerprint: list[tuple[int, str]],
) -> bool:
    if source is None or not chunks:
        return False
    source_metadata = (
        source.metadata_json
        if isinstance(source.metadata_json, dict)
        else {}
    )
    return bool(
        not source_metadata.get("indexStale")
        and all(chunk.is_active for chunk in chunks)
        and source.content_hash == content_hash
        and source.source_version == source_version
        and source.publish_status == publish_status
        and existing_chunk_fingerprint == expected_chunk_fingerprint
    )


def _get_material_job_metadata(metadata_json: dict | list | None) -> dict[str, object]:
    if not isinstance(metadata_json, dict):
        raise invalid_request_error("Material index job metadata is missing")

    required_keys = [
        "title",
        "resourceUrl",
        "storagePath",
        "sizeBytes",
        "moduleStatus",
        "storageProvider",
        "objectKey",
    ]
    for key in required_keys:
        value = metadata_json.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise invalid_request_error(f"Material index job metadata field '{key}' is required")

    return metadata_json


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _get_prompt_log_user_id(metadata: dict[str, object]) -> int:
    educator_id = metadata.get("educatorId")
    if isinstance(educator_id, int) and educator_id > 0:
        return educator_id
    return 0


def _truncate_text(value: str, limit: int = 4000) -> str:
    normalized = value.strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit]


def _to_publish_status(module_status: str) -> AIPublishStatus:
    normalized = module_status.strip().lower()
    if normalized == "published":
        return AIPublishStatus.PUBLISHED
    if normalized == "archived":
        return AIPublishStatus.ARCHIVED
    return AIPublishStatus.DRAFT


def _to_markdown_content(
    *,
    content_text: str,
    content_type: str | None,
    object_key: str,
) -> str | None:
    suffix = object_key.lower().rsplit(".", 1)[-1] if "." in object_key else ""
    if content_type == "text/markdown" or suffix == "md":
        return content_text
    return None


def _compute_retry_delay_seconds(attempt_count: int) -> int:
    base_delay = max(1, settings.ai_index_job_retry_base_seconds)
    max_delay = max(base_delay, settings.ai_index_job_retry_max_seconds)
    exponent = max(0, attempt_count - 1)
    return min(base_delay * (2 ** exponent), max_delay)


def _should_auto_retry(*, exc: Exception, stage: str) -> bool:
    normalized_message = f"{type(exc).__name__}: {exc}".lower()
    normalized_stage = stage.lower()

    if normalized_stage == "metadata_validation":
        return False

    non_retryable_markers = [
        "metadata field",
        "is required",
        "unsupported",
        "unable to decode",
        "content is empty",
        "dimension mismatch",
        "vector magnitude is zero",
        "not found",
        "no such file",
        "does not exist",
    ]
    if any(marker in normalized_message for marker in non_retryable_markers):
        return False

    retryable_markers = [
        "timeout",
        "timed out",
        "too many requests",
        "rate limit",
        "429",
        "500",
        "502",
        "503",
        "504",
        "temporarily unavailable",
        "service unavailable",
        "connection reset",
        "connection refused",
        "connection aborted",
        "server disconnected",
        "broken pipe",
        "eof",
        "name resolution",
        "max retries exceeded",
        "deadlock",
        "could not serialize",
        "lock timeout",
        "database is locked",
    ]
    if any(marker in normalized_message for marker in retryable_markers):
        return True

    if normalized_stage.startswith(
        ("embedding_chunk_", "embedding_model_", "embedding_partial")
    ):
        return True

    if normalized_stage in {
        "content_extraction",
        "index_write",
        "multi_vector_index_write",
    }:
        return True

    return False
