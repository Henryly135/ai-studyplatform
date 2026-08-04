from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.prompts import PromptTemplate
from app.models.ai_prompt_logs import AIPromptCallType
from app.services.chat.langchain_rag_service import (
    _build_plain_chat_input,
    _build_rag_chat_input,
    _serialize_history_for_logs,
    render_rag_user_prompt,
    serialize_retrieved_context,
)
from app.services.chat.rag_retrieval_service import RetrievalResult, RetrievedChunk


def _retrieval_result() -> RetrievalResult:
    return RetrievalResult(
        query_text="summarize module",
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id=1,
                source_id=2,
                material_id=3,
                module_id=4,
                course_id=5,
                chunk_index=0,
                chunk_text="Intro to neural networks",
                heading_path="Week 1",
                score=0.87654,
                distance=0.12346,
                metadata_json={"title": "week1.pdf"},
            )
        ],
        raw_retrieved_chunks=[],
        chat_model_id="glm:glm-4.7",
        query_embedding_model="embedding-model",
        query_embedding_version="embedding-model@1024",
        index_status="ready",
        indexed_chunk_count=1,
        total_chunk_count=1,
        index_coverage=1.0,
        latency_ms=12,
        filters_json={},
        retrieval_trace_json={},
    )


def test_serialize_retrieved_context_renders_source_metadata() -> None:
    # Tests retrieved chunks render source metadata for RAG prompts.
    context = serialize_retrieved_context(_retrieval_result())

    assert "[Source 1]" in context
    assert "course_id: 5" in context
    assert "module_id: 4" in context
    assert "material_id: 3" in context
    assert "heading_path: Week 1" in context
    assert "score: 0.8765" in context
    assert "Intro to neural networks" in context


def test_render_rag_user_prompt_includes_context_and_question() -> None:
    # Tests rendered RAG user prompts include context and trimmed question.
    prompt = render_rag_user_prompt(
        current_user_message=" What is covered? ",
        retrieval_result=_retrieval_result(),
    )

    assert "Retrieved learning context:" in prompt
    assert "User question:\nWhat is covered?" in prompt
    assert "Intro to neural networks" in prompt


def test_build_chat_inputs_trim_question_and_preserve_history() -> None:
    # Tests plain and RAG chat inputs trim questions and keep history objects.
    history = [SystemMessage(content="rules"), HumanMessage(content="hello")]
    plain_input = _build_plain_chat_input("  question  ", history)
    rag_input = _build_rag_chat_input(
        current_user_message="  question  ",
        retrieval_result=_retrieval_result(),
        conversation_history=history,
    )

    assert plain_input == {"history": history, "question": "question"}
    assert rag_input["history"] is history
    assert rag_input["question"] == "question"
    assert "Intro to neural networks" in rag_input["retrieved_context"]


def test_serialize_history_for_logs_handles_string_and_list_content() -> None:
    # Tests history log serialization handles string and list content.
    history = [
        HumanMessage(content="hello"),
        HumanMessage(content=[{"type": "text", "text": "list content"}]),
    ]

    assert _serialize_history_for_logs(history) == [
        {"type": "human", "content": "hello"},
        {"type": "human", "content": "{'type': 'text', 'text': 'list content'}"},
    ]


def test_prompt_template_smoke() -> None:
    # Tests PromptTemplate construction preserves key fields.
    prompt = PromptTemplate(
        name="test_prompt",
        call_type=AIPromptCallType.CHAT,
        system_instruction="Be helpful.",
        description="Test prompt",
    )

    assert prompt.name == "test_prompt"
    assert prompt.system_instruction == "Be helpful."
