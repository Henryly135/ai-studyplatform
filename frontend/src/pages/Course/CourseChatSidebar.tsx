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
  const [status, setStatus] = useState("Open the assistant to start a module conversation.");
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
    setStatus("Loading module sessions...");

    void listModuleChatSessions(moduleUuid)
      .then((data) => {
        if (cancelled) {
          return;
        }

        setSessions(data);
        setStatus(
          data.length > 0
            ? "Select a session or send a new message to start another one."
            : "No sessions for this module yet. Send a message to create one."
        );
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setSessions([]);
        setStatus(error instanceof Error ? error.message : "Failed to load module sessions.");
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
      setStatus("Select a session or send a new message to start another one.");
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
    setStatus("Loading session...");

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
      setStatus("Session loaded.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load the selected session.");
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
    setStatus(activeSessionUuid ? "Sending to current session..." : "Creating a new session...");

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
      setStatus("Assistant replied.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to send the message.");
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
          aria-label="Resize chat sidebar"
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
                  setStatus("Select a session or send a new message to start another one.");
                }}
                aria-label="Back to sessions"
              >
                <LuArrowLeft size={18} aria-hidden="true" />
              </button>
            ) : (
              <div className="course-chat-back course-chat-back-placeholder" aria-hidden="true" />
            )}

            <div className="course-chat-header-copy">
              <span>{isViewingSession ? "Session" : "Module assistant"}</span>
              <strong>{isViewingSession ? activeSession?.title || "Session" : moduleTitle}</strong>
            </div>

            <button type="button" className="course-chat-close" onClick={onClose} aria-label="Close chatbot">
              <LuX size={18} aria-hidden="true" />
            </button>
          </header>

          {!isViewingSession ? (
            <section className="course-chat-session-list" aria-label="Module chat sessions">
              <div className="course-chat-section-heading">
                <h3>Sessions</h3>
                <span className="course-chat-status-chip">{sessions.length} total</span>
              </div>

              <div className="course-chat-session-items">
                {isLoadingSessions ? <p className="course-chat-muted">Loading sessions...</p> : null}
                {!isLoadingSessions && sessions.length === 0 ? (
                  <p className="course-chat-muted">No sessions under this module yet.</p>
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
                      <strong>{session.title || "Untitled session"}</strong>
                      <span>{formatRelativeTimestamp(session.last_message_at)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <section className="course-chat-conversation">
              <div className="course-chat-section-heading">
                <h3>{activeSession ? activeSession.title || "Current session" : "Session"}</h3>
              </div>

              <div ref={messageViewportRef} className="course-chat-message-list" aria-live="polite">
                {messages.length === 0 ? (
                  <div className="course-chat-empty-state">No visible messages in this session yet.</div>
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
                placeholder="Ask about this module..."
                disabled={isSending}
              />
              <button
                type="submit"
                className="course-chat-send"
                disabled={!composerValue.trim() || isSending}
                aria-label="Send message"
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
