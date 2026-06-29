from __future__ import annotations

from app.core.uuid_codec import decode_course_uuid, decode_module_uuid
from app.services.chat.custom_pgvector_retriever import CustomPgvectorRetriever, CustomPgvectorRetrieverInput
from app.services.workflows.quiz_generation.schemas import RetrievalContextChunkRead, RetrievalContextRead


class QuizGenerationRetrievalService:
    def __init__(self, session) -> None:
        self.session = session
        self._retriever: CustomPgvectorRetriever | None = None

    @property
    def retriever(self) -> CustomPgvectorRetriever:
        if self._retriever is None:
            self._retriever = CustomPgvectorRetriever(self.session)
        return self._retriever

    def load_context(
        self,
        *,
        educator_id: int,
        course_uuid: str,
        module_uuid: str,
        quiz_title: str,
        module_title: str,
        question_count: int,
        additional_instructions: str | None,
    ) -> RetrievalContextRead:
        course_id = decode_course_uuid(course_uuid)
        module_id = decode_module_uuid(module_uuid)
        query_text = (
            f"Generate {question_count} multiple-choice quiz questions for module '{module_title}' "
            f"under quiz '{quiz_title}'."
        )
        if additional_instructions:
            query_text = f"{query_text} Additional instructions: {additional_instructions.strip()}"

        retrieval_result = self.retriever.invoke(
            CustomPgvectorRetrieverInput(
                user_id=educator_id,
                query_text=query_text,
                course_id=course_id,
                module_id=module_id,
                session_id=None,
                message_id=None,
                top_k=5,
            )
        )

        chunks = [
            RetrievalContextChunkRead(
                chunkId=chunk.chunk_id,
                materialId=chunk.material_id,
                moduleId=chunk.module_id,
                headingPath=chunk.heading_path,
                score=chunk.score,
                content=chunk.chunk_text,
            )
            for chunk in retrieval_result.retrieved_chunks
        ]
        return RetrievalContextRead(
            usedRetrieval=bool(chunks),
            queryText=query_text,
            topK=5,
            chunkCount=len(chunks),
            chunks=chunks,
        )
