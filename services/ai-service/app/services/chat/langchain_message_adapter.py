from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.services.chat.chat_history_service import ChatHistoryMessage


def to_langchain_messages(history: list[ChatHistoryMessage]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for entry in history:
        content = entry.content_text.strip()
        if not content:
            continue

        if entry.role == "user":
            messages.append(HumanMessage(content=content))
        elif entry.role == "assistant":
            messages.append(AIMessage(content=content))
        elif entry.role == "system":
            messages.append(SystemMessage(content=content))
        elif entry.role == "tool":
            messages.append(ToolMessage(content=content, tool_call_id=f"history-{entry.message_id}"))
        else:
            messages.append(HumanMessage(content=content))
    return messages
