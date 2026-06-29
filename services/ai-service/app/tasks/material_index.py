from hashlib import sha256
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.time import now_local
from app.db.session import SessionLocal
from app.models.ai_index_jobs import AIJobStatus
from app.models.ai_knowledge_sources import AIPublishStatus, AIKnowledgeSourceType, AIVisibilityScope
from app.models.ai_prompt_logs import AIPromptStatus
from app.repositories.ai_embedding_logs_repository import AIEmbeddingLogsRepository
from app.repositories.ai_index_jobs_repository import AIIndexJobsRepository
from app.repositories.ai_knowledge_chunks_repository import ChunkCreate
from app.services.indexing.embedding_service import EmbeddingService
from app.services.indexing.knowledge_indexing_service import KnowledgeIndexingService, SourceUpsert
from app.services.indexing.material_content_service import MaterialContentRequest, MaterialContentService
from app.services.indexing.text_chunking_service import TextChunkingService
from platform_common.errors import invalid_request_error


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

    try:
        content_service = MaterialContentService()
        chunking_service = TextChunkingService()
        embedding_service = EmbeddingService()
        indexing_service = KnowledgeIndexingService(session)

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

        jobs.update_status(
            job,
            status=AIJobStatus.RUNNING,
            worker_id=str(getattr(self.request, "hostname", "") or getattr(self.request, "id", "") or "ai-worker"),
            next_retry_at=None,
            locked_at=current_time,
            started_at=current_time,
            finished_at=None,
            error_message=None,
            attempt_count=job.attempt_count + 1,
        )
        session.commit()

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
        job.content_hash = content_hash

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

        # Stage 6: For each chunk, generate embeddings and prepare for database insertion 
        chunk_rows: list[ChunkCreate] = []
        prompt_log_user_id = _get_prompt_log_user_id(metadata)
        for text_chunk in text_chunks:
            stage = f"embedding_chunk_{text_chunk.chunk_index}"
            embedding_input = text_chunk.chunk_text
            token_count = embedding_service.count_document_tokens(text=embedding_input)
            try:
                embedding_result = embedding_service.embed_document(
                    text=embedding_input,
                    title=str(metadata["title"]),
                )
                embedding_logs.create(
                    job_id=job.job_id,
                    user_id=prompt_log_user_id,
                    course_id=job.course_id,
                    module_id=job.module_id,
                    material_id=job.material_id,
                    chunk_index=text_chunk.chunk_index,
                    chunk_hash=text_chunk.chunk_hash,
                    model_name=embedding_result.embedding_model,
                    model_version=embedding_result.embedding_version,
                    task_type=embedding_result.task_type,
                    title=str(metadata["title"]),
                    input_text=_truncate_text(embedding_input),
                    input_chars=len(embedding_input),
                    provider_input_tokens=token_count.provider_input_tokens,
                    provider_total_tokens=token_count.provider_total_tokens,
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
                session.commit()
            except Exception as exc:
                embedding_logs.create(
                    job_id=job.job_id,
                    user_id=prompt_log_user_id,
                    course_id=job.course_id,
                    module_id=job.module_id,
                    material_id=job.material_id,
                    chunk_index=text_chunk.chunk_index,
                    chunk_hash=text_chunk.chunk_hash,
                    model_name=settings.ai_embedding_model,
                    model_version=settings.ai_embedding_version,
                    task_type=settings.ai_embedding_task_type,
                    title=str(metadata["title"]),
                    input_text=_truncate_text(embedding_input),
                    input_chars=len(embedding_input),
                    provider_input_tokens=token_count.provider_input_tokens,
                    provider_total_tokens=token_count.provider_total_tokens,
                    vector_length=None,
                    output_dimensionality=settings.ai_embedding_output_dimension,
                    request_json={
                        "tokenCount": token_count.request_json,
                        "embedding": {
                            "model": settings.ai_embedding_model,
                            "contents_preview": embedding_input[:500],
                            "config": {
                                "task_type": settings.ai_embedding_task_type,
                                "output_dimensionality": settings.ai_embedding_output_dimension,
                                "title": str(metadata["title"]),
                            },
                        },
                    },
                    response_json={
                        "tokenCount": token_count.response_json,
                    },
                    latency_ms=None,
                    status=AIPromptStatus.FAILED,
                    error_message=f"{type(exc).__name__}: {exc}",
                    trace_id=None,
                )
                session.commit()
                raise
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
                    embedding_model=embedding_result.embedding_model,
                    embedding_version=embedding_result.embedding_version,
                    embedding=embedding_result.vector,
                    metadata_json={
                        "title": metadata["title"],
                        "objectKey": metadata["objectKey"],
                        "contentType": metadata.get("contentType"),
                    },
                )
            )


        # Stage 7: Upsert the knowledge source and its chunks into the database
        stage = "index_write"
        indexing_result = indexing_service.replace_source_chunks(
            source_data=SourceUpsert(
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
                embedding_model=settings.ai_embedding_model,
                embedding_version=settings.ai_embedding_version,
                source_version=str(metadata["objectKey"]),
                metadata_json=source_metadata,
                created_by=None,
                updated_by=None,
                origin_event_id=job.trigger_event_id,
            ),
            chunks=chunk_rows,
        )

        processed_at = now_local()
        jobs.update_status(
            job,
            status=AIJobStatus.SUCCESS,
            worker_id=job.worker_id,
            next_retry_at=None,
            locked_at=job.locked_at,
            started_at=job.started_at,
            finished_at=processed_at,
        )
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
            "processedAt": processed_at.isoformat(timespec="seconds"),
        }
    
    except Exception as exc:
        session.rollback()
        job = jobs.get_by_id(jobId)
        if job is not None:
            if not isinstance(job.metadata_json, dict):
                job.metadata_json = {}
            current_attempt = job.attempt_count or 0
            error_message = f"[{stage}] {type(exc).__name__}: {exc}"
            if _should_auto_retry(exc=exc, stage=stage) and current_attempt < settings.ai_index_job_max_auto_retries:
                retry_delay_seconds = _compute_retry_delay_seconds(current_attempt)
                retry_at = now_local() + timedelta(seconds=retry_delay_seconds)
                job.metadata_json = {
                    **job.metadata_json,
                    "lastErrorStage": stage,
                    "lastErrorType": type(exc).__name__,
                    "lastErrorMessage": str(exc),
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
                            "retryDispatchErrorMessage": str(dispatch_exc),
                        }
                        jobs.update_status(
                            retry_job,
                            status=AIJobStatus.FAILED,
                            worker_id=retry_job.worker_id,
                            locked_at=retry_job.locked_at,
                            started_at=retry_job.started_at,
                            finished_at=now_local(),
                            next_retry_at=None,
                            error_message=f"[retry_dispatch] {type(dispatch_exc).__name__}: {dispatch_exc}",
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
                "lastErrorMessage": str(exc),
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

    if normalized_stage.startswith("embedding_chunk_"):
        return True

    if normalized_stage in {"content_extraction", "index_write"}:
        return True

    return False
