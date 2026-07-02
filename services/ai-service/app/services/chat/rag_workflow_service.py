from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
import re
from time import sleep
from uuid import uuid4

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from langchain_core.messages import BaseMessage
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.prompts import get_prompt_template
from app.models.ai_prompt_logs import AIPromptStatus
from app.services.provider_error_messages import (
    AI_PROVIDER_CONFIGURATION_UNAVAILABLE,
    AI_PROVIDER_TEMPORARILY_UNAVAILABLE,
)
from app.services.chat.chat_history_service import ChatHistoryService
from app.services.chat.custom_pgvector_retriever import CustomPgvectorRetriever, CustomPgvectorRetrieverInput
from app.services.chat.langchain_message_adapter import to_langchain_messages
from app.services.chat.langchain_rag_service import render_rag_user_prompt, run_langchain_chat
from app.services.chat.rag_retrieval_service import RetrievalResult

_COURSE_CONTEXT_MARKERS = {
    "module",
    "lecture",
    "chapter",
    "course",
    "material",
    "document",
    "pdf",
    "topic",
    "topics",
    "cover",
    "covers",
    "covered",
    "this module",
    "this lecture",
    "this chapter",
    "课程",
    "模块",
    "讲义",
    "文档",
    "材料",
    "这门课",
    "这个模块",
    "这一讲",
    "这一章",
    "讲了什么",
    "讲了哪些",
}

_STOPWORDS = {
    "what",
    "which",
    "does",
    "this",
    "that",
    "with",
    "from",
    "into",
    "about",
    "would",
    "could",
    "should",
    "please",
    "tell",
    "give",
    "show",
    "explain",
    "module",
    "lecture",
    "chapter",
    "course",
    "document",
    "topic",
    "topics",
    "cover",
    "covers",
    "covered",
    "讲了",
    "哪些",
    "什么",
    "这个",
    "这个模块",
    "课程",
    "模块",
    "文档",
}

_TIME_SENSITIVE_MARKERS = {
    "today",
    "today's",
    "current",
    "currently",
    "latest",
    "now",
    "news",
    "weather",
    "forecast",
    "temperature",
    "score",
    "scores",
    "result",
    "results",
    "match",
    "game",
    "games",
    "fixture",
    "fixtures",
    "stock",
    "price",
    "prices",
    "market",
    "time",
    "date",
    "nba",
    "nfl",
    "mlb",
    "epl",
    "今天",
    "今日",
    "现在",
    "当前",
    "最新",
    "新闻",
    "日期",
    "时间",
    "气温",
    "温度",
    "天气",
    "赛况",
    "比赛",
    "比分",
    "股价",
    "汇率",
}


class AIChatConfigurationError(RuntimeError):
    """Raised when the chat feature is not configured."""


class AIChatQuotaError(RuntimeError):
    """Raised when the upstream model provider rejects the request due to quota/rate limits."""


class AIModelInvocationError(RuntimeError):
    """Raised when model execution fails after retries with classified provider metadata."""

    def __init__(
        self,
        message: str,
        *,
        provider_error_type: str,
        orchestrator: str,
        chain_name: str,
        fallback_used: bool,
    ) -> None:
        super().__init__(message)
        self.provider_error_type = provider_error_type
        self.orchestrator = orchestrator
        self.chain_name = chain_name
        self.fallback_used = fallback_used


@dataclass(frozen=True)
class AIChatReplyResult:
    reply: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None
    request_json: dict | list | None
    response_json: dict | list | None
    status: AIPromptStatus
    error_message: str | None
    trace_id: str


@dataclass(frozen=True)
class ChatWorkflowResult:
    reply_result: AIChatReplyResult
    prompt_template_name: str
    retrieval_result: RetrievalResult | None
    used_retrieval: bool
    retrieval_context_text: str | None
    conversation_history: list[BaseMessage]

    @property
    def sources(self) -> list[dict[str, object]]:
        if not self.used_retrieval or self.retrieval_result is None:
            return []
        return [
            {
                "material_id": chunk.material_id,
                "module_id": chunk.module_id,
                "heading_path": chunk.heading_path,
                "chunk_index": chunk.chunk_index,
                "score": round(chunk.score, 6),
            }
            for chunk in self.retrieval_result.retrieved_chunks
        ]


def _build_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise AIChatConfigurationError(AI_PROVIDER_CONFIGURATION_UNAVAILABLE)
    return genai.Client(api_key=settings.gemini_api_key)


def _extract_usage_value(usage_metadata: object, *names: str) -> int | None:
    for name in names:
        if isinstance(usage_metadata, dict) and usage_metadata.get(name) is not None:
            return int(usage_metadata[name])

        value = getattr(usage_metadata, name, None)
        if value is not None:
            return int(value)
    return None


def _safe_usage_metadata(usage_metadata: object) -> dict | None:
    if usage_metadata is None:
        return None
    if isinstance(usage_metadata, dict):
        return usage_metadata

    result: dict[str, int | str | None] = {}
    for name in (
        "prompt_token_count",
        "input_tokens",
        "candidates_token_count",
        "output_tokens",
        "total_token_count",
        "total_tokens",
    ):
        value = getattr(usage_metadata, name, None)
        if value is not None:
            result[name] = int(value)
    return result or None


def build_rag_user_prompt(*, current_user_message: str, retrieval_result: RetrievalResult) -> str:
    return render_rag_user_prompt(
        current_user_message=current_user_message,
        retrieval_result=retrieval_result,
    )


def _has_retrieved_context(retrieval_result: RetrievalResult | None) -> bool:
    return retrieval_result is not None and len(retrieval_result.retrieved_chunks) > 0


def _is_course_scoped_question(message: str) -> bool:
    normalized = " ".join(message.lower().split())
    return any(marker in normalized for marker in _COURSE_CONTEXT_MARKERS)


def _extract_query_keywords(message: str) -> set[str]:
    normalized = message.lower()
    latin_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", normalized))
    chinese_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", message))
    return {token for token in latin_tokens | chinese_tokens if token not in _STOPWORDS}


def _has_grounding_overlap(message: str, retrieval_result: RetrievalResult | None) -> bool:
    if retrieval_result is None or not retrieval_result.raw_retrieved_chunks:
        return False

    keywords = _extract_query_keywords(message)
    if not keywords:
        return False

    searchable_text = " ".join(chunk.chunk_text.lower() for chunk in retrieval_result.raw_retrieved_chunks)
    return any(keyword.lower() in searchable_text for keyword in keywords)


def should_use_retrieval(message: str, retrieval_result: RetrievalResult | None) -> bool:
    if not _has_retrieved_context(retrieval_result):
        return False

    if _is_course_scoped_question(message):
        return True

    if _has_grounding_overlap(message, retrieval_result):
        return True

    top_score = retrieval_result.raw_retrieved_chunks[0].score if retrieval_result.raw_retrieved_chunks else 0.0
    return top_score >= 0.8


def _is_time_sensitive_question(message: str) -> bool:
    normalized = " ".join(message.lower().split())
    return any(marker in normalized for marker in _TIME_SENSITIVE_MARKERS)


def _build_time_sensitive_unavailable_reply() -> str:
    return (
        "I can help with course materials and general knowledge, but I do not have a live data source for "
        "real-time information such as current weather, today's sports results, breaking news, market prices, "
        "or the current date and time. Please check a real-time service for that information."
    )


def _classify_provider_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "resource_exhausted" in message or "quota" in message or "429" in message:
        return "quota"
    if "timeout" in message or "timed out" in message or "deadline" in message:
        return "provider_timeout"
    if (
        "503" in message
        or "unavailable" in message
        or "connection" in message
        or "network" in message
        or "temporary failure" in message
        or "reset by peer" in message
    ):
        return "transient_network_error"
    if "invalid" in message or "context" in message or "400" in message or "argument" in message:
        return "invalid_session_or_context"
    return "unknown_provider_error"


def _is_retryable_provider_error(provider_error_type: str) -> bool:
    return provider_error_type in {"provider_timeout", "transient_network_error"}


def _invoke_with_short_retries(
    *,
    invoke_fn,
    orchestrator: str,
    chain_name: str,
    fallback_used: bool,
) -> tuple[object, str | None]:
    delays = [0.35, 0.8]
    last_exc: Exception | None = None
    for attempt in range(len(delays) + 1):
        try:
            return invoke_fn(), None
        except genai_errors.ClientError as exc:
            provider_error_type = _classify_provider_error(exc)
            if provider_error_type == "quota":
                raise AIChatQuotaError(
                    "Gemini quota exceeded. Please retry shortly or check billing/quota limits."
                ) from exc
            if attempt < len(delays) and _is_retryable_provider_error(provider_error_type):
                sleep(delays[attempt])
                last_exc = exc
                continue
            raise AIModelInvocationError(
                AI_PROVIDER_TEMPORARILY_UNAVAILABLE,
                provider_error_type=provider_error_type,
                orchestrator=orchestrator,
                chain_name=chain_name,
                fallback_used=fallback_used,
            ) from exc
        except Exception as exc:
            provider_error_type = _classify_provider_error(exc)
            if attempt < len(delays) and _is_retryable_provider_error(provider_error_type):
                sleep(delays[attempt])
                last_exc = exc
                continue
            raise AIModelInvocationError(
                AI_PROVIDER_TEMPORARILY_UNAVAILABLE,
                provider_error_type=provider_error_type,
                orchestrator=orchestrator,
                chain_name=chain_name,
                fallback_used=fallback_used,
            ) from exc

    raise AIModelInvocationError(
        AI_PROVIDER_TEMPORARILY_UNAVAILABLE,
        provider_error_type=_classify_provider_error(last_exc or RuntimeError("unknown error")),
        orchestrator=orchestrator,
        chain_name=chain_name,
        fallback_used=fallback_used,
    )


def generate_chat_reply(
    *,
    current_user_message: str,
    prompt_template_name: str = "chat_reply_v1",
    retrieval_result: RetrievalResult | None = None,
    conversation_history: list[BaseMessage] | None = None,
) -> AIChatReplyResult:
    started_at = perf_counter()
    trace_id = str(uuid4())
    prompt = get_prompt_template(prompt_template_name)
    use_retrieval = should_use_retrieval(current_user_message, retrieval_result)
    chain_name = "rag_chat" if use_retrieval else "plain_chat"

    if not use_retrieval and _is_time_sensitive_question(current_user_message):
        latency_ms = int((perf_counter() - started_at) * 1000)
        guardrail_reply = _build_time_sensitive_unavailable_reply()
        return AIChatReplyResult(
            reply=guardrail_reply,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=latency_ms,
            request_json={
                "model": None,
                "contents": current_user_message,
                "config": None,
                "prompt_template_name": "time_sensitive_guardrail_v1",
                "orchestrator": "guardrail",
                "chain_name": "time_sensitive_guardrail_v1",
                "fallback_used": False,
                "provider_error_type": None,
            },
            response_json={
                "text": guardrail_reply,
                "guardrail": "time_sensitive_without_live_data",
                "orchestrator": "guardrail",
                "chain_name": "time_sensitive_guardrail_v1",
                "fallback_used": False,
                "provider_error_type": None,
            },
            status=AIPromptStatus.SUCCESS,
            error_message=None,
            trace_id=trace_id,
        )

    langchain_failure: AIModelInvocationError | None = None
    if settings.ai_chat_orchestrator.strip().lower() == "langchain":
        try:
            chain_result, _ = _invoke_with_short_retries(
                invoke_fn=lambda: run_langchain_chat(
                    current_user_message=current_user_message,
                    prompt=prompt,
                    retrieval_result=retrieval_result if use_retrieval else None,
                    conversation_history=conversation_history,
                ),
                orchestrator="langchain",
                chain_name=chain_name,
                fallback_used=False,
            )
            latency_ms = int((perf_counter() - started_at) * 1000)
            request_json = dict(chain_result.request_json)
            request_json.update(
                {
                    "orchestrator": "langchain",
                    "chain_name": chain_name,
                    "fallback_used": False,
                    "provider_error_type": None,
                }
            )
            response_json = dict(chain_result.response_json)
            response_json.update(
                {
                    "orchestrator": "langchain",
                    "chain_name": chain_name,
                    "fallback_used": False,
                    "provider_error_type": None,
                }
            )
            return AIChatReplyResult(
                reply=chain_result.reply or "Sorry, I could not generate a response this time.",
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                latency_ms=latency_ms,
                request_json=request_json,
                response_json=response_json,
                status=AIPromptStatus.SUCCESS,
                error_message=None,
                trace_id=trace_id,
            )
        except AIModelInvocationError as exc:
            langchain_failure = exc

    client = _build_client()
    prompt_input_text = (
        build_rag_user_prompt(
            current_user_message=current_user_message,
            retrieval_result=retrieval_result,
        )
        if use_retrieval
        else current_user_message
    )
    request_json = {
        "model": settings.ai_demo_model_name,
        "contents": prompt_input_text,
        "config": {
            "system_instruction": prompt.system_instruction,
            "temperature": 0.5,
            "max_output_tokens": settings.ai_chat_max_output_tokens,
        },
        "prompt_template_name": prompt.name,
        "orchestrator": "direct_sdk",
        "chain_name": chain_name,
        "fallback_used": settings.ai_chat_orchestrator.strip().lower() == "langchain",
        "provider_error_type": None,
        "fallback_source_error_type": langchain_failure.provider_error_type if langchain_failure else None,
    }
    try:
        response, _ = _invoke_with_short_retries(
            invoke_fn=lambda: client.models.generate_content(
                model=settings.ai_demo_model_name,
                contents=prompt_input_text,
                config=types.GenerateContentConfig(
                    system_instruction=prompt.system_instruction,
                    temperature=0.5,
                    max_output_tokens=settings.ai_chat_max_output_tokens,
                ),
            ),
            orchestrator="direct_sdk",
            chain_name=chain_name,
            fallback_used=settings.ai_chat_orchestrator.strip().lower() == "langchain",
        )
    except AIChatQuotaError:
        raise
    except AIModelInvocationError as exc:
        request_json["provider_error_type"] = exc.provider_error_type
        raise

    latency_ms = int((perf_counter() - started_at) * 1000)
    usage_metadata = getattr(response, "usage_metadata", None)
    prompt_tokens = _extract_usage_value(usage_metadata, "prompt_token_count", "input_tokens")
    completion_tokens = _extract_usage_value(usage_metadata, "candidates_token_count", "output_tokens")
    total_tokens = _extract_usage_value(usage_metadata, "total_token_count", "total_tokens")
    response_json = {
        "text": getattr(response, "text", None),
        "usage_metadata": _safe_usage_metadata(usage_metadata),
        "orchestrator": "direct_sdk",
        "chain_name": chain_name,
        "fallback_used": settings.ai_chat_orchestrator.strip().lower() == "langchain",
        "provider_error_type": None,
        "fallback_source_error_type": langchain_failure.provider_error_type if langchain_failure else None,
    }

    if getattr(response, "text", None):
        return AIChatReplyResult(
            reply=response.text.strip(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            request_json=request_json,
            response_json=response_json,
            status=AIPromptStatus.SUCCESS,
            error_message=None,
            trace_id=trace_id,
        )

    return AIChatReplyResult(
        reply="Sorry, I could not generate a response this time.",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        request_json=request_json,
        response_json=response_json,
        status=AIPromptStatus.SUCCESS,
        error_message=None,
        trace_id=trace_id,
    )


class RAGWorkflowService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.history_service = ChatHistoryService(session)
        self.retriever = CustomPgvectorRetriever(session)

    def execute_chat_workflow(
        self,
        *,
        user_id: int,
        session_id: int,
        message_id: int,
        current_user_message: str,
        course_id: int | None,
        module_id: int | None,
    ) -> ChatWorkflowResult:
        is_time_sensitive_non_course = _is_time_sensitive_question(current_user_message) and not _is_course_scoped_question(
            current_user_message
        )

        conversation_history = [] if is_time_sensitive_non_course else to_langchain_messages(
            self.history_service.list_visible_history(
                session_id=session_id,
                before_message_id=message_id,
            )
        )

        retrieval_result: RetrievalResult | None = None
        if course_id is not None and not is_time_sensitive_non_course:
            retrieval_result = self.retriever.invoke(
                CustomPgvectorRetrieverInput(
                    user_id=user_id,
                    query_text=current_user_message.strip(),
                    course_id=course_id,
                    module_id=module_id,
                    session_id=session_id,
                    message_id=message_id,
                    top_k=settings.ai_retrieval_top_k,
                )
            )

        use_retrieval = False if is_time_sensitive_non_course else should_use_retrieval(
            current_user_message, retrieval_result
        )
        prompt_template_name = "chat_rag_v1" if use_retrieval else "chat_reply_v1"
        reply_result = generate_chat_reply(
            current_user_message=current_user_message.strip(),
            prompt_template_name=prompt_template_name,
            retrieval_result=retrieval_result if use_retrieval else None,
            conversation_history=conversation_history,
        )
        retrieval_context_text = (
            build_rag_user_prompt(
                current_user_message=current_user_message.strip(),
                retrieval_result=retrieval_result,
            )
            if use_retrieval and retrieval_result is not None
            else None
        )
        return ChatWorkflowResult(
            reply_result=reply_result,
            prompt_template_name=prompt_template_name,
            retrieval_result=retrieval_result,
            used_retrieval=use_retrieval,
            retrieval_context_text=retrieval_context_text,
            conversation_history=conversation_history,
        )
