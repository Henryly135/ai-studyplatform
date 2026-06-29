from __future__ import annotations

from dataclasses import dataclass

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from sqlalchemy.orm import Session

from app.services.chat.rag_retrieval_service import RagRetrievalService, RetrievalResult


@dataclass(frozen=True)
class CustomPgvectorRetrieverInput:
    user_id: int
    query_text: str
    course_id: int
    module_id: int | None
    session_id: int | None
    message_id: int | None
    top_k: int


class CustomPgvectorRetriever:
    def __init__(self, session: Session) -> None:
        self._retrieval_service = RagRetrievalService(session)

    def invoke(self, payload: CustomPgvectorRetrieverInput) -> RetrievalResult:
        return self._retrieval_service.retrieve(
            user_id=payload.user_id,
            query_text=payload.query_text,
            course_id=payload.course_id,
            module_id=payload.module_id,
            session_id=payload.session_id,
            message_id=payload.message_id,
            top_k=payload.top_k,
        )

    def as_runnable(self) -> RunnableSerializable[dict[str, object], RetrievalResult]:
        return RunnableLambda(self._invoke_from_mapping)

    def _invoke_from_mapping(self, payload: dict[str, object]) -> RetrievalResult:
        return self.invoke(
            CustomPgvectorRetrieverInput(
                user_id=int(payload["user_id"]),
                query_text=str(payload["query_text"]),
                course_id=int(payload["course_id"]),
                module_id=int(payload["module_id"]) if payload.get("module_id") is not None else None,
                session_id=int(payload["session_id"]) if payload.get("session_id") is not None else None,
                message_id=int(payload["message_id"]) if payload.get("message_id") is not None else None,
                top_k=int(payload.get("top_k", 5)),
            )
        )
