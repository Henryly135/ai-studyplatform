from __future__ import annotations

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.core.prompts import PromptTemplate
from app.services.chat.rag_retrieval_service import RetrievalResult


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
