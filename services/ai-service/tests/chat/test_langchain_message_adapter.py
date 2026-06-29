from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.services.chat.chat_history_service import ChatHistoryMessage
from app.services.chat.langchain_message_adapter import to_langchain_messages


def test_to_langchain_messages_maps_roles_and_skips_blank_content() -> None:
    # Tests chat history roles map to LangChain messages and blank entries are skipped.
    messages = to_langchain_messages(
        [
            ChatHistoryMessage(message_id=1, role="user", content_text=" hello "),
            ChatHistoryMessage(message_id=2, role="assistant", content_text="hi"),
            ChatHistoryMessage(message_id=3, role="system", content_text=" rules "),
            ChatHistoryMessage(message_id=4, role="tool", content_text="lookup"),
            ChatHistoryMessage(message_id=5, role="unknown", content_text="fallback"),
            ChatHistoryMessage(message_id=6, role="user", content_text="   "),
        ]
    )

    assert [type(message) for message in messages] == [
        HumanMessage,
        AIMessage,
        SystemMessage,
        ToolMessage,
        HumanMessage,
    ]
    assert [message.content for message in messages] == ["hello", "hi", "rules", "lookup", "fallback"]
    assert messages[3].tool_call_id == "history-4"
