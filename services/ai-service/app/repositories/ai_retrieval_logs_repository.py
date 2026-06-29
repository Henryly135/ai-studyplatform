from sqlalchemy.orm import Session

from app.models.ai_retrieval_logs import AIRetrievalLog


class AIRetrievalLogsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        session_id: int | None,
        message_id: int | None,
        user_id: int,
        user_query: str,
        results_json: dict | list,
        retrieval_mode: str | None = None,
        rewritten_query: str | None = None,
        query_embedding_model: str | None = None,
        filters_json: dict | list | None = None,
        top_k: int = 5,
        latency_ms: int | None = None,
    ) -> AIRetrievalLog:
        retrieval_log = AIRetrievalLog(
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            retrieval_mode=retrieval_mode,
            user_query=user_query,
            rewritten_query=rewritten_query,
            query_embedding_model=query_embedding_model,
            filters_json=filters_json,
            top_k=top_k,
            results_json=results_json,
            latency_ms=latency_ms,
        )
        self.session.add(retrieval_log)
        self.session.flush()
        return retrieval_log
