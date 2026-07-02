from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSerializable
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.core.prompts import PromptTemplate
from app.services.chat.rag_retrieval_service import RetrievalResult


@dataclass(frozen=True)
class LangChainChatExecutionResult:
    reply: str
    request_json: dict[str, object]
    response_json: dict[str, object]


def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.ai_demo_model_name,
        google_api_key=settings.gemini_api_key,
        temperature=0.5,
        max_output_tokens=settings.ai_chat_max_output_tokens,
    )


def serialize_retrieved_context(retrieval_result: RetrievalResult) -> str:
    context_blocks: list[str] = []
    for index, chunk in enumerate(retrieval_result.retrieved_chunks, start=1):
        context_blocks.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"course_id: {chunk.course_id}",
                    f"module_id: {chunk.module_id}",
                    f"material_id: {chunk.material_id}",
                    f"heading_path: {chunk.heading_path or ''}",
                    f"score: {chunk.score:.4f}",
                    "content:",
                    chunk.chunk_text,
                ]
            )
        )
    return "\n\n".join(context_blocks)


def render_rag_user_prompt(*, current_user_message: str, retrieval_result: RetrievalResult) -> str:
    context_text = serialize_retrieved_context(retrieval_result) or "[No retrieved context]"
    return (
        "Retrieved learning context:\n"
        f"{context_text}\n\n"
        "User question:\n"
        f"{current_user_message.strip()}\n\n"
        "Answer the user using the retrieved context when possible. "
        "If the question asks what a module, lecture, chapter, or document covers, "
        "provide a complete summary of the relevant topics from the retrieved context "
        "as a short bullet list. If the context is insufficient, say so clearly."
    )


def build_plain_chat_prompt(prompt: PromptTemplate) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", prompt.system_instruction),
            MessagesPlaceholder("history", optional=True),
            ("human", "{question}"),
        ]
    )


def build_rag_chat_prompt(prompt: PromptTemplate) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", prompt.system_instruction),
            MessagesPlaceholder("history", optional=True),
            (
                "human",
                (
                    "Retrieved learning context:\n"
                    "{retrieved_context}\n\n"
                    "User question:\n"
                    "{question}\n\n"
                    "Answer the user using the retrieved context when possible. "
                    "If the question asks what a module, lecture, chapter, or document covers, "
                    "provide a complete summary of the relevant topics from the retrieved context "
                    "as a short bullet list. If the context is insufficient, say so clearly."
                ),
            ),
        ]
    )


def build_plain_chat_chain(prompt: PromptTemplate) -> RunnableSerializable[dict[str, str], str]:
    return build_plain_chat_prompt(prompt) | _build_llm() | StrOutputParser()


def build_rag_chat_chain(prompt: PromptTemplate) -> RunnableSerializable[dict[str, str], str]:
    return build_rag_chat_prompt(prompt) | _build_llm() | StrOutputParser()


def _serialize_history_for_logs(history: list[BaseMessage]) -> list[dict[str, str]]:
    serialized: list[dict[str, str]] = []
    for message in history:
        content = message.content
        if isinstance(content, list):
            rendered_content = " ".join(str(item) for item in content)
        else:
            rendered_content = str(content)
        serialized.append(
            {
                "type": message.type,
                "content": rendered_content,
            }
        )
    return serialized


def _build_plain_chat_input(
    current_user_message: str,
    conversation_history: list[BaseMessage],
) -> dict[str, object]:
    return {
        "history": conversation_history,
        "question": current_user_message.strip(),
    }


def _build_rag_chat_input(
    *,
    current_user_message: str,
    retrieval_result: RetrievalResult,
    conversation_history: list[BaseMessage],
) -> dict[str, object]:
    return {
        "history": conversation_history,
        "retrieved_context": serialize_retrieved_context(retrieval_result),
        "question": current_user_message.strip(),
    }


def run_langchain_plain_chat(
    *,
    current_user_message: str,
    prompt: PromptTemplate,
    conversation_history: list[BaseMessage] | None = None,
) -> LangChainChatExecutionResult:
    chain = build_plain_chat_chain(prompt)
    history = conversation_history or []
    prompt_input = _build_plain_chat_input(current_user_message, history)
    reply = chain.invoke(prompt_input).strip()
    return LangChainChatExecutionResult(
        reply=reply,
        request_json={
            "model": settings.ai_demo_model_name,
            "prompt_template_name": prompt.name,
            "orchestrator": "langchain",
            "chain_name": "plain_chat",
            "fallback_used": False,
            "provider_error_type": None,
            "input": {
                "history": _serialize_history_for_logs(history),
                "question": prompt_input["question"],
            },
        },
        response_json={
            "text": reply,
            "orchestrator": "langchain",
            "chain_name": "plain_chat",
            "fallback_used": False,
            "provider_error_type": None,
        },
    )


def run_langchain_rag_chat(
    *,
    current_user_message: str,
    prompt: PromptTemplate,
    retrieval_result: RetrievalResult,
    conversation_history: list[BaseMessage] | None = None,
) -> LangChainChatExecutionResult:
    chain = build_rag_chat_chain(prompt)
    history = conversation_history or []
    prompt_input = _build_rag_chat_input(
        current_user_message=current_user_message,
        retrieval_result=retrieval_result,
        conversation_history=history,
    )
    reply = chain.invoke(prompt_input).strip()
    return LangChainChatExecutionResult(
        reply=reply,
        request_json={
            "model": settings.ai_demo_model_name,
            "prompt_template_name": prompt.name,
            "orchestrator": "langchain",
            "chain_name": "rag_chat",
            "fallback_used": False,
            "provider_error_type": None,
            "input": {
                "history": _serialize_history_for_logs(history),
                "retrieved_context": prompt_input["retrieved_context"],
                "question": prompt_input["question"],
            },
        },
        response_json={
            "text": reply,
            "orchestrator": "langchain",
            "chain_name": "rag_chat",
            "fallback_used": False,
            "provider_error_type": None,
        },
    )


def run_langchain_chat(
    *,
    current_user_message: str,
    prompt: PromptTemplate,
    retrieval_result: RetrievalResult | None,
    conversation_history: list[BaseMessage] | None = None,
) -> LangChainChatExecutionResult:
    if retrieval_result is not None and retrieval_result.retrieved_chunks:
        return run_langchain_rag_chat(
            current_user_message=current_user_message,
            prompt=prompt,
            retrieval_result=retrieval_result,
            conversation_history=conversation_history,
        )

    return run_langchain_plain_chat(
        current_user_message=current_user_message,
        prompt=prompt,
        conversation_history=conversation_history,
    )
