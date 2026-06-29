import { useEffect, useMemo, useState } from "react";
import { LuArrowLeft } from "react-icons/lu";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { getChatSessionDetail, listChatSessions } from "../../services/chat";
import { getCourses } from "../../services/course";
import type { ChatSessionDetail, ChatSessionSummary } from "../../types/chat";
import type { CourseRecord } from "../../types/course";
import "./HomePage.css";

function formatSessionTimestamp(value: string | null) {
  if (!value) {
    return "No activity yet";
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

function HomeAiPage() {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [courses, setCourses] = useState<CourseRecord[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailErrorMessage, setDetailErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void listChatSessions()
      .then((data) => {
        if (!cancelled) {
          setSessions(data);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to load AI sessions.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    void getCourses()
      .then((data) => {
        if (!cancelled) {
          setCourses(data.items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCourses([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const courseTitleMap = useMemo(() => {
    const courseTitles = new Map<string, string>();

    courses.forEach((course) => {
      courseTitles.set(course.courseUuid, course.title);
    });

    return courseTitles;
  }, [courses]);

  function getSessionContextLabel(session: ChatSessionSummary) {
    return session.course_uuid
      ? courseTitleMap.get(session.course_uuid) ?? "Unknown course"
      : "Unknown course";
  }

  function handleBackToSessions() {
    setActiveSession(null);
    setDetailErrorMessage(null);
    setDetailLoading(false);
  }

  function handleOpenSession(sessionUuid: string) {
    setDetailLoading(true);
    setDetailErrorMessage(null);

    void getChatSessionDetail(sessionUuid)
      .then((detail) => {
        setActiveSession(detail);
      })
      .catch((error) => {
        setDetailErrorMessage(
          error instanceof Error ? error.message : "Failed to load the selected session."
        );
      })
      .finally(() => {
        setDetailLoading(false);
      });
  }

  return (
    <section className="home-ai-page">
      <div className="home-ai-hero">
        <span className="home-content-badge">AI</span>
        <h1>AI Workspace</h1>
        <p>
          Review all chat sessions here. Module recommendations stay as a placeholder until
          the backend recommendation flow is ready.
        </p>
      </div>

      <div className="home-ai-grid">
        <article className={`home-ai-panel ${activeSession ? "home-ai-panel-detail-mode" : ""}`}>
          {activeSession ? (
            <>
              <div className="home-ai-panel-heading home-ai-detail-heading">
                <button type="button" className="home-ai-back" onClick={handleBackToSessions}>
                  <LuArrowLeft size={18} aria-hidden="true" />
                  <span>Back to sessions</span>
                </button>
                <div className="home-ai-detail-meta">
                  <h2>{activeSession.session.title || "Untitled session"}</h2>
                  <span>{formatSessionTimestamp(activeSession.session.last_message_at)}</span>
                </div>
              </div>

              {detailErrorMessage ? <p className="home-ai-muted">{detailErrorMessage}</p> : null}

              <div className="home-ai-detail-body">
                {detailLoading ? <p className="home-ai-muted">Loading conversation...</p> : null}
                {!detailLoading && activeSession.messages.length === 0 ? (
                  <p className="home-ai-muted">No messages were found in this session.</p>
                ) : null}

                {!detailLoading && activeSession.messages.length > 0 ? (
                  <div className="home-ai-message-list">
                    {activeSession.messages.map((message) => (
                      <article
                        key={message.message_id}
                        className={`home-ai-message home-ai-message-${message.role === "user" ? "user" : "assistant"}`}
                      >
                        <div className="home-ai-message-bubble">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.content_text}
                          </ReactMarkdown>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <div className="home-ai-panel-heading">
                <h2>All Sessions</h2>
                <span>{loading ? "Loading..." : `${sessions.length} total`}</span>
              </div>

              {loading ? <p className="home-ai-muted">Loading sessions...</p> : null}
              {errorMessage ? <p className="home-ai-muted">{errorMessage}</p> : null}
              {!loading && !errorMessage && sessions.length === 0 ? (
                <p className="home-ai-muted">No AI sessions found yet.</p>
              ) : null}

              <div className="home-ai-session-list">
                {sessions.map((session) => (
                  <button
                    key={session.session_uuid}
                    type="button"
                    className="home-ai-session-card"
                    onClick={() => handleOpenSession(session.session_uuid)}
                  >
                    <div className="home-ai-session-meta">
                      <strong>{session.title || "Untitled session"}</strong>
                      <span>{formatSessionTimestamp(session.last_message_at)}</span>
                    </div>
                    <p className="home-ai-session-context">{getSessionContextLabel(session)}</p>
                  </button>
                ))}
              </div>
            </>
          )}
        </article>

        <article className="home-ai-panel">
          <div className="home-ai-panel-heading">
            <h2>Module Recommendations</h2>
            <span>Coming soon</span>
          </div>
          <div className="home-ai-placeholder">
            Module recommendations for learners will appear here after the backend
            recommendation flow is implemented.
          </div>
        </article>
      </div>
    </section>
  );
}

export default HomeAiPage;
