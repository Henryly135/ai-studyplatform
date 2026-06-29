from sqlalchemy.orm import Session

from app.models.ai_embedding_logs import AIEmbeddingLog
from app.models.ai_prompt_logs import AIPromptStatus


class AIEmbeddingLogsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        job_id: int | None,
        user_id: int,
        course_id: int | None,
        module_id: int | None,
        material_id: int | None,
        chunk_index: int | None,
        chunk_hash: str | None,
        model_name: str,
        model_version: str | None,
        task_type: str | None,
        title: str | None,
        input_text: str,
        input_chars: int,
        status: AIPromptStatus,
        provider_input_tokens: int | None = None,
        provider_total_tokens: int | None = None,
        vector_length: int | None = None,
        output_dimensionality: int | None = None,
        request_json: dict | list | None = None,
        response_json: dict | list | None = None,
        latency_ms: int | None = None,
        error_message: str | None = None,
        trace_id: str | None = None,
    ) -> AIEmbeddingLog:
        embedding_log = AIEmbeddingLog(
            job_id=job_id,
            user_id=user_id,
            course_id=course_id,
            module_id=module_id,
            material_id=material_id,
            chunk_index=chunk_index,
            chunk_hash=chunk_hash,
            model_name=model_name,
            model_version=model_version,
            task_type=task_type,
            title=title,
            input_text=input_text,
            input_chars=input_chars,
            provider_input_tokens=provider_input_tokens,
            provider_total_tokens=provider_total_tokens,
            vector_length=vector_length,
            output_dimensionality=output_dimensionality,
            request_json=request_json,
            response_json=response_json,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            trace_id=trace_id,
        )
        self.session.add(embedding_log)
        self.session.flush()
        return embedding_log
