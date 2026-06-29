from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.ai_prompt_logs import AIPromptStatus
from app.services.chat.rag_retrieval_service import RetrievalResult, RetrievedChunk
from app.services.chat.rag_workflow_service import (
    AIChatQuotaError,
    AIModelInvocationError,
    ChatWorkflowResult,
    _build_time_sensitive_unavailable_reply,
    _classify_provider_error,
    _extract_query_keywords,
    _extract_usage_value,
    _has_grounding_overlap,
    _is_course_scoped_question,
    _is_retryable_provider_error,
    _is_time_sensitive_question,
    _safe_usage_metadata,
    build_rag_user_prompt,
    generate_chat_reply,
    should_use_retrieval,
)


def _retrieval_result(*, score: float = 0.9, text: str = "neural network optimization") -> RetrievalResult:
    chunk = RetrievedChunk(
        chunk_id=1,
        source_id=2,
        material_id=3,
        module_id=4,
        course_id=5,
        chunk_index=0,
        chunk_text=text,
        heading_path="Week 1",
        score=score,
        distance=1 - score,
        metadata_json={},
    )
    return RetrievalResult(
        query_text="query",
        retrieved_chunks=[chunk] if score >= 0.45 else [],
        raw_retrieved_chunks=[chunk],
        query_embedding_model="embedding",
        latency_ms=1,
        filters_json={},
        retrieval_trace_json={"results": []},
    )


def test_usage_metadata_helpers_read_dicts_objects_and_empty_values() -> None:
    # Tests token usage extraction from provider dict/object metadata.
    usage_object = SimpleNamespace(prompt_token_count=2, candidates_token_count=3, total_token_count=5)

    assert _extract_usage_value({"input_tokens": "7"}, "prompt_token_count", "input_tokens") == 7
    assert _extract_usage_value(usage_object, "prompt_token_count") == 2
    assert _extract_usage_value({}, "missing") is None
    assert _safe_usage_metadata(usage_object) == {
        "prompt_token_count": 2,
        "candidates_token_count": 3,
        "total_token_count": 5,
    }
    assert _safe_usage_metadata({"total_tokens": 9}) == {"total_tokens": 9}
    assert _safe_usage_metadata(None) is None


def test_retrieval_decision_uses_course_markers_overlap_and_score() -> None:
    # Tests when chat should switch from plain response to RAG response.
    assert should_use_retrieval("What does this module cover?", _retrieval_result(score=0.5)) is True
    assert should_use_retrieval("Explain optimization", _retrieval_result(score=0.5)) is True
    assert should_use_retrieval("Unrelated question", _retrieval_result(score=0.82, text="other")) is True
    assert should_use_retrieval("Unrelated question", _retrieval_result(score=0.5, text="other")) is False
    assert should_use_retrieval("Anything", None) is False


def test_message_classification_helpers_detect_keywords() -> None:
    # Tests course-scoped, time-sensitive, and keyword extraction helpers.
    assert _is_course_scoped_question("What does this lecture cover?") is True
    assert _is_course_scoped_question("What is Python?") is False
    assert _is_time_sensitive_question("What is the latest score today?") is True
    assert _is_time_sensitive_question("Explain recursion") is False
    assert "optimization" in _extract_query_keywords("Please explain optimization in this module")


def test_grounding_overlap_requires_keywords_in_retrieved_text() -> None:
    # Tests grounding overlap only succeeds when meaningful query terms appear in context.
    assert _has_grounding_overlap("Explain optimization", _retrieval_result(text="optimization notes")) is True
    assert _has_grounding_overlap("Explain databases", _retrieval_result(text="optimization notes")) is False
    assert _has_grounding_overlap("Explain", _retrieval_result(text="optimization notes")) is False
    assert _has_grounding_overlap("Explain optimization", None) is False


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("quota exceeded 429", "quota"),
        ("deadline timed out", "provider_timeout"),
        ("503 service unavailable", "transient_network_error"),
        ("invalid argument 400", "invalid_session_or_context"),
        ("strange failure", "unknown_provider_error"),
    ],
)
def test_provider_error_classification(message, expected) -> None:
    # Tests provider error messages are mapped to stable categories.
    assert _classify_provider_error(RuntimeError(message)) == expected


def test_retryable_provider_error_categories() -> None:
    # Tests which provider error categories are retried by short retry wrapper.
    assert _is_retryable_provider_error("provider_timeout") is True
    assert _is_retryable_provider_error("transient_network_error") is True
    assert _is_retryable_provider_error("quota") is False


def test_time_sensitive_guardrail_reply_is_returned_without_provider_call() -> None:
    # Tests current/live-data questions use the guardrail response without Gemini.
    result = generate_chat_reply(current_user_message="What is the latest NBA score today?")

    assert result.status == AIPromptStatus.SUCCESS
    assert result.request_json["orchestrator"] == "guardrail"
    assert result.response_json["guardrail"] == "time_sensitive_without_live_data"
    assert "do not have a live data source" in result.reply


def test_build_time_sensitive_unavailable_reply_mentions_live_data_limits() -> None:
    # Tests the live-data guardrail message explains unsupported real-time data.
    reply = _build_time_sensitive_unavailable_reply()

    assert "real-time information" in reply
    assert "current weather" in reply


def test_build_rag_user_prompt_delegates_to_rendered_retrieval_context() -> None:
    # Tests RAG workflow prompt rendering includes current question and context.
    prompt = build_rag_user_prompt(
        current_user_message="Summarize",
        retrieval_result=_retrieval_result(text="module content"),
    )

    assert "module content" in prompt
    assert "Summarize" in prompt


def test_chat_workflow_sources_only_return_when_retrieval_was_used() -> None:
    # Tests ChatWorkflowResult source serialization is gated by used_retrieval.
    reply_result = SimpleNamespace(reply="ok")
    with_sources = ChatWorkflowResult(
        reply_result=reply_result,
        prompt_template_name="chat_rag_v1",
        retrieval_result=_retrieval_result(score=0.8765439),
        used_retrieval=True,
        retrieval_context_text="context",
        conversation_history=[],
    )
    without_sources = ChatWorkflowResult(
        reply_result=reply_result,
        prompt_template_name="chat_reply_v1",
        retrieval_result=_retrieval_result(),
        used_retrieval=False,
        retrieval_context_text=None,
        conversation_history=[],
    )

    assert with_sources.sources == [
        {
            "material_id": 3,
            "module_id": 4,
            "heading_path": "Week 1",
            "chunk_index": 0,
            "score": 0.876544,
        }
    ]
    assert without_sources.sources == []


def test_invoke_with_short_retries_retries_transient_failures(monkeypatch) -> None:
    # Tests retry wrapper retries transient errors and returns the successful value.
    from app.services.chat import rag_workflow_service

    calls = {"count": 0}
    monkeypatch.setattr(rag_workflow_service, "sleep", lambda _: None)

    def _invoke():
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("timeout")
        return "ok"

    value, error = rag_workflow_service._invoke_with_short_retries(
        invoke_fn=_invoke,
        orchestrator="direct_sdk",
        chain_name="plain_chat",
        fallback_used=False,
    )

    assert value == "ok"
    assert error is None
    assert calls["count"] == 2


def test_invoke_with_short_retries_raises_model_error_for_non_retryable_failure() -> None:
    # Tests retry wrapper converts non-retryable provider errors to model invocation errors.
    from app.services.chat import rag_workflow_service

    with pytest.raises(AIModelInvocationError) as exc_info:
        rag_workflow_service._invoke_with_short_retries(
            invoke_fn=lambda: (_ for _ in ()).throw(RuntimeError("invalid argument")),
            orchestrator="direct_sdk",
            chain_name="plain_chat",
            fallback_used=True,
        )

    assert exc_info.value.provider_error_type == "invalid_session_or_context"
    assert exc_info.value.fallback_used is True


def test_invoke_with_short_retries_maps_quota_client_errors(monkeypatch) -> None:
    # Tests quota-classified provider errors become AIChatQuotaError.
    from app.services.chat import rag_workflow_service

    class FakeClientError(Exception):
        pass

    monkeypatch.setattr(rag_workflow_service.genai_errors, "ClientError", FakeClientError)

    with pytest.raises(AIChatQuotaError):
        rag_workflow_service._invoke_with_short_retries(
            invoke_fn=lambda: (_ for _ in ()).throw(FakeClientError("quota 429")),
            orchestrator="direct_sdk",
            chain_name="plain_chat",
            fallback_used=False,
        )
