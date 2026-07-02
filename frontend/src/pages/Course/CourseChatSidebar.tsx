import { useEffect, useMemo, useRef, useState } from "react";
import { LuArrowLeft, LuArrowUp, LuX } from "react-icons/lu";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { getChatSessionDetail, listModuleChatSessions, sendChatMessage } from "../../services/chat";
import type { CourseChatMessage, ChatSessionSummary } from "../../types/chat";

type CourseChatSidebarProps = {
  isOpen: boolean;
  courseUuid: string;
  moduleUuid: string;
  moduleTitle: string;
  onClose: () => void;
  onResizeStart: () => void;
};

function formatRelativeTimestamp(value: string | null) {
  if (!value) {
    return "New";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return "Recent";
  }

  return new Intl.DateTimeFormat("en-AU", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp);
}

function mapMessagesToConversation(messages: CourseChatMessage[], pendingText: string) {
  const nextMessages = [...messages];
  const nextId = nextMessages.length > 0 ? Math.max(...nextMessages.map((entry) => entry.id)) + 1 : 1;

  nextMessages.push({
    id: nextId,
    role: "user",
    text: pendingText,
  });

  return nextMessages;
}

function CourseChatSidebar({
  isOpen,
  courseUuid,
  moduleUuid,
  moduleTitle,
  onClose,
  onResizeStart,
}: CourseChatSidebarProps) {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionUuid, setActiveSessionUuid] = useState<string | null>(null);
  const [messages, setMessages] = useState<CourseChatMessage[]>([]);
  const [composerValue, setComposerValue] = useState("");
  const [status, setStatus] = useState("打开助手开始模块对话。");
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isLoadingSessionDetail, setIsLoadingSessionDetail] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const messageViewportRef = useRef<HTMLDivElement | null>(null);
  const isViewingSession = activeSessionUuid !== null;

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let cancelled = false;
    setIsLoadingSessions(true);
    setStatus("正在加载模块会话...");

    void listModuleChatSessions(moduleUuid)
      .then((data) => {
        if (cancelled) {
          return;
        }

        setSessions(data);
        setStatus(
          data.length > 0
            ? "选择一个会话，或发送新消息开始另一个会话。"
            : "该模块暂无会话，发送消息即可创建。"
        );
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setSessions([]);
        setStatus(error instanceof Error ? error.message : "模块会话加载失败。");
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingSessions(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, moduleUuid]);

  useEffect(() => {
    setActiveSessionUuid(null);
    setMessages([]);
    setComposerValue("");
    if (isOpen) {
      setStatus("选择一个会话，或发送新消息开始另一个会话。");
    }
  }, [moduleUuid, isOpen]);

  useEffect(() => {
    if (!messageViewportRef.current) {
      return;
    }

    messageViewportRef.current.scrollTop = messageViewportRef.current.scrollHeight;
  }, [messages, isOpen, activeSessionUuid]);

  const activeSession = useMemo(
    () => sessions.find((entry) => entry.session_uuid === activeSessionUuid) ?? null,
    [sessions, activeSessionUuid]
  );

  const loadSession = async (sessionUuid: string) => {
    setIsLoadingSessionDetail(true);
    setStatus("正在加载会话...");

    try {
      const detail = await getChatSessionDetail(sessionUuid);
      setActiveSessionUuid(detail.session.session_uuid);
      setMessages(
        detail.messages
          .filter((entry) => entry.role === "user" || entry.role === "assistant")
          .map((entry) => ({
            id: entry.message_id,
            role: entry.role === "assistant" ? "assistant" : "user",
            text: entry.content_text,
          }))
      );
      setStatus("会话已加载。");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "所选会话加载失败。");
    } finally {
      setIsLoadingSessionDetail(false);
    }
  };

  const refreshSessions = async (nextActiveSessionUuid: string | null) => {
    const updatedSessions = await listModuleChatSessions(moduleUuid);
    setSessions(updatedSessions);
    if (nextActiveSessionUuid) {
      setActiveSessionUuid(nextActiveSessionUuid);
    }
  };

  const handleSend = async () => {
    const trimmedMessage = composerValue.trim();
    if (!trimmedMessage || isSending || isLoadingSessionDetail) {
      return;
    }

    const wasViewingSession = isViewingSession;
    setComposerValue("");
    setMessages((current) => mapMessagesToConversation(current, trimmedMessage));
    if (!wasViewingSession) {
      setActiveSessionUuid("__pending__");
    }
    setIsSending(true);
    setStatus(activeSessionUuid ? "正在发送到当前会话..." : "正在创建新会话...");

    try {
      const response = await sendChatMessage({
        courseUuid,
        moduleUuid,
        message: trimmedMessage,
        sessionUuid: activeSessionUuid,
      });

      await refreshSessions(response.session_uuid);
      setActiveSessionUuid(response.session_uuid);
      setMessages((current) => [
        ...current,
        {
          id: response.assistant_message_id,
          role: "assistant",
          text: response.reply,
        },
      ]);
      setStatus("助手已回复。");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "消息发送失败。");
      if (wasViewingSession) {
        setMessages((current) => current.slice(0, -1));
      } else {
        setActiveSessionUuid(null);
        setMessages([]);
      }
      setComposerValue(trimmedMessage);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <>
      <div
        className={`course-chat-overlay${isOpen ? " course-chat-overlay-visible" : ""}`}
        onClick={onClose}
        aria-hidden={!isOpen}
      />

      <aside className={`course-chat-sidebar${isOpen ? " course-chat-sidebar-open" : ""}`} aria-hidden={!isOpen}>
        <div
          className="course-chat-resize-handle"
          onMouseDown={onResizeStart}
          role="separator"
          aria-orientation="vertical"
          aria-label="调整聊天侧栏大小"
          tabIndex={-1}
        />
        <div className="course-chat-sidebar-shell">
          <header className="course-chat-header">
            {isViewingSession ? (
              <button
                type="button"
                className="course-chat-back"
                onClick={() => {
                  setActiveSessionUuid(null);
                  setMessages([]);
                  setStatus("选择一个会话，或发送新消息开始另一个会话。");
                }}
                aria-label="返回会话列表"
              >
                <LuArrowLeft size={18} aria-hidden="true" />
              </button>
            ) : (
              <div className="course-chat-back course-chat-back-placeholder" aria-hidden="true" />
            )}

            <div className="course-chat-header-copy">
              <span>{isViewingSession ? "Session" : "模块助手"}</span>
              <strong>{isViewingSession ? activeSession?.title || "Session" : moduleTitle}</strong>
            </div>

            <button type="button" className="course-chat-close" onClick={onClose} aria-label="关闭聊天助手">
              <LuX size={18} aria-hidden="true" />
            </button>
          </header>

          {!isViewingSession ? (
            <section className="course-chat-session-list" aria-label="模块聊天会话">
              <div className="course-chat-section-heading">
                <h3>会话</h3>
                <span className="course-chat-status-chip">{sessions.length}总计</span>
              </div>

              <div className="course-chat-session-items">
                {isLoadingSessions ? <p className="course-chat-muted">正在加载会话...</p> : null}
                {!isLoadingSessions && sessions.length === 0 ? (
                  <p className="course-chat-muted">该模块下暂无会话。</p>
                ) : null}
                {sessions.map((session) => (
                  <button
                    key={session.session_uuid}
                    type="button"
                    className="course-chat-session-item"
                    onClick={() => void loadSession(session.session_uuid)}
                    disabled={isLoadingSessionDetail}
                  >
                    <div className="course-chat-session-meta">
                      <strong>{session.title || "未命名会话"}</strong>
                      <span>{formatRelativeTimestamp(session.last_message_at)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <section className="course-chat-conversation">
              <div className="course-chat-section-heading">
                <h3>{activeSession ? activeSession.title || "当前会话" : "Session"}</h3>
              </div>

              <div ref={messageViewportRef} className="course-chat-message-list" aria-live="polite">
                {messages.length === 0 ? (
                  <div className="course-chat-empty-state">该会话暂无可见消息。</div>
                ) : (
                  messages.map((entry) => (
                    <article
                      key={entry.id}
                      className={`course-chat-message course-chat-message-${entry.role}`}
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.text}</ReactMarkdown>
                    </article>
                  ))
                )}
              </div>
            </section>
          )}

          <form
            className="course-chat-composer"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSend();
            }}
          >
            <p className="course-chat-status-text">{status}</p>
            <div className="course-chat-composer-row">
              <textarea
                value={composerValue}
                onChange={(event) => setComposerValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
                placeholder="询问这个模块..."
                disabled={isSending}
              />
              <button
                type="submit"
                className="course-chat-send"
                disabled={!composerValue.trim() || isSending}
                aria-label="发送消息"
              >
                <LuArrowUp size={18} aria-hidden="true" />
              </button>
            </div>
          </form>
        </div>
      </aside>
    </>
  );
}

export default CourseChatSidebar;
