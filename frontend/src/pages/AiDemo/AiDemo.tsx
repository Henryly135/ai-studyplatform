import { useCallback, useEffect, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import "./AiDemo.css";
import { getCurrentUser } from "../../services/auth";
import {
  buildAuthHeaders,
  clearStoredSession,
  getStoredAccessToken,
  handleAuthenticationFailureFromResponse,
} from "../../services/api";


type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
};

type DemoChatResponse = {
  session_uuid: string;
  user_message_id: number;
  assistant_message_id: number;
  reply: string;
};

type ChatSuccessResponse = {
  success: true;
  data: DemoChatResponse;
};

type ChatSessionSummary = {
  session_uuid: string;
  user_id: number;
  course_uuid: string | null;
  module_uuid: string | null;
  session_type: string;
  title: string | null;
  status: string;
  message_count: number;
  summary_text: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
};

type ChatSessionMessage = {
  message_id: number;
  session_uuid: string;
  role: "user" | "assistant" | "system" | "tool";
  message_type: string;
  parent_message_id: number | null;
  content_text: string;
  created_at: string;
};

type ChatSessionDetail = {
  session: ChatSessionSummary;
  messages: ChatSessionMessage[];
};

type APIErrorResponse = {
  success?: false;
  error?: {
    code: string;
    message: string;
  };
  detail?: string;
};

type AiDemoLocationState = {
  courseUuid?: string | null;
  moduleUuid?: string | null;
};

const CHAT_API_URL = "/api/ai/chat";
const CHAT_SESSIONS_API_URL = "/api/ai/chat/sessions";

function isInvalidCredentialsError(error: unknown) {
  return error instanceof Error && error.message === "Invalid credentials";
}

function AiDemo() {
  const navigate = useNavigate();
  const location = useLocation();
  const { sessionUuid } = useParams();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("Checking login status...");
  const [loading, setLoading] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionDetailLoading, setSessionDetailLoading] = useState(false);
  const [sessionUuidState, setSessionUuidState] = useState<string | null>(sessionUuid ?? null);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const locationState = (location.state ?? null) as AiDemoLocationState | null;
  const initialCourseUuid = locationState?.courseUuid ?? null;
  const initialModuleUuid = locationState?.moduleUuid ?? null;
  const [courseUuid, setCourseUuid] = useState<string | null>(initialCourseUuid);
  const [moduleUuid, setModuleUuid] = useState<string | null>(initialModuleUuid);
  const buildContextState = (nextCourseUuid: string | null, nextModuleUuid: string | null): AiDemoLocationState => ({
    courseUuid: nextCourseUuid,
    moduleUuid: nextModuleUuid,
  });

  const clearSessionState = () => {
    clearStoredSession();
  };

  const resetCurrentSession = () => {
    setSessionUuidState(null);
    setMessages([]);
    setMessage("");
    setCourseUuid(initialCourseUuid);
    setModuleUuid(initialModuleUuid);
    setStatus("Ready to start a new session.");
    navigate("/ai-demo", {
      replace: true,
      state: buildContextState(initialCourseUuid, initialModuleUuid),
    });
  };

  const fetchSessions = async (accessToken: string) => {
    void accessToken;
    setSessionsLoading(true);

    try {
      const response = await fetch(CHAT_SESSIONS_API_URL, {
        headers: buildAuthHeaders(),
      });
      const data = (await response.json()) as ChatSessionSummary[] | APIErrorResponse;
      handleAuthenticationFailureFromResponse(response.status, data);
      if (!response.ok) {
        throw new Error(
          "error" in data && data.error?.message
            ? data.error.message
            : "detail" in data && data.detail
              ? data.detail
              : "Failed to load sessions."
        );
      }

      setSessions(data as ChatSessionSummary[]);
    } finally {
      setSessionsLoading(false);
    }
  };

  const loadSessionDetail = useCallback(async (targetSessionUuid: string, accessToken: string) => {
    void accessToken;
    setSessionDetailLoading(true);

    try {
      const response = await fetch(`${CHAT_SESSIONS_API_URL}/${targetSessionUuid}`, {
        headers: buildAuthHeaders(),
      });
      const data = (await response.json()) as ChatSessionDetail | APIErrorResponse;
      handleAuthenticationFailureFromResponse(response.status, data);
      if (!response.ok) {
        throw new Error(
          "error" in data && data.error?.message
            ? data.error.message
            : "detail" in data && data.detail
              ? data.detail
              : "Failed to load session."
        );
      }

      const detail = data as ChatSessionDetail;
      setSessionUuidState(detail.session.session_uuid);
      setCourseUuid(detail.session.course_uuid);
      setModuleUuid(detail.session.module_uuid);
      setMessages(
        detail.messages
          .filter((entry) => entry.role === "user" || entry.role === "assistant")
          .map((entry) => ({
            id: entry.message_id,
            role: entry.role === "assistant" ? "assistant" : "user",
            text: entry.content_text,
          }))
      );
      navigate(`/ai-demo/${detail.session.session_uuid}`, {
        replace: true,
        state: buildContextState(detail.session.course_uuid, detail.session.module_uuid),
      });
      setStatus("Loaded session.");
    } finally {
      setSessionDetailLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    let cancelled = false;

    const verifySession = async () => {
      const accessToken = localStorage.getItem("accessToken");
      if (!accessToken) {
        navigate("/login", { replace: true });
        return;
      }

      try {
        const currentUser = await getCurrentUser(accessToken);
        if (cancelled) {
          return;
        }

        localStorage.setItem("currentUser", JSON.stringify(currentUser));
        try {
          await fetchSessions(accessToken);
          if (cancelled) {
            return;
          }
          if (sessionUuid) {
            await loadSessionDetail(sessionUuid, accessToken);
            if (cancelled) {
              return;
            }
          } else {
            setSessionUuidState(null);
          }
          setStatus("Authenticated. Ready.");
        } catch (error) {
          if (cancelled) {
            return;
          }
          if (isInvalidCredentialsError(error)) {
            clearSessionState();
            navigate("/login", { replace: true });
            return;
          }

          setSessionUuidState(null);
          setMessages([]);
          setStatus(
            error instanceof Error
              ? `AI demo is available, but session data failed to load: ${error.message}`
              : "AI demo is available, but session data failed to load."
          );
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        if (isInvalidCredentialsError(error)) {
          clearSessionState();
          navigate("/login", { replace: true });
          return;
        }

        setStatus(
          error instanceof Error
            ? `Unable to verify login status: ${error.message}`
            : "Unable to verify login status."
        );
      } finally {
        if (!cancelled) {
          setAuthChecking(false);
        }
      }
    };

    void verifySession();

    return () => {
      cancelled = true;
    };
  }, [navigate, sessionUuid, loadSessionDetail]);

  const appendMessage = (role: ChatMessage["role"], text: string) => {
    setMessages((current) => [
      ...current,
      {
        id: current.length + 1,
        role,
        text,
      },
    ]);
  };

  const sendMessage = async () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || loading || authChecking) {
      setStatus("Please enter a message.");
      return;
    }
    try {
      getStoredAccessToken();
    } catch {
      navigate("/login", { replace: true });
      return;
    }

    appendMessage("user", trimmedMessage);
    setMessage("");
    setLoading(true);
    setStatus("AI is thinking...");

    try {
      const response = await fetch(CHAT_API_URL, {
        method: "POST",
        headers: buildAuthHeaders({
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          session_uuid: sessionUuidState,
          course_uuid: courseUuid,
          module_uuid: moduleUuid,
          message: trimmedMessage,
        }),
      });

      const data = (await response.json()) as ChatSuccessResponse | APIErrorResponse;
      handleAuthenticationFailureFromResponse(response.status, data);
      if (!response.ok) {
        throw new Error(
          "error" in data && data.error?.message
            ? data.error.message
            : "detail" in data && data.detail
              ? data.detail
              : "Unknown error"
        );
      }

      const successData = (data as ChatSuccessResponse).data;
      setSessionUuidState(successData.session_uuid);
      navigate(`/ai-demo/${successData.session_uuid}`, {
        replace: true,
        state: buildContextState(courseUuid, moduleUuid),
      });
      appendMessage("assistant", successData.reply);
      await fetchSessions(getStoredAccessToken());
      setStatus("Message sent successfully.");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Unknown error";
      if (errorMessage === "Invalid credentials") {
        clearSessionState();
        navigate("/login", { replace: true });
        return;
      }

      appendMessage("assistant", `Error: ${errorMessage}`);
      setStatus("Send failed.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (sessionUuidState) {
      return;
    }
    setCourseUuid(initialCourseUuid);
    setModuleUuid(initialModuleUuid);
  }, [initialCourseUuid, initialModuleUuid, sessionUuidState]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await sendMessage();
  };

  const handleKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await sendMessage();
    }
  };

  if (authChecking) {
    return (
      <div className="ai-demo-page">
        <div className="ai-demo-shell">
          <header className="ai-demo-header">
            <span className="ai-demo-badge">AI Demo</span>
            <h1>Learning Assistance Chatbot</h1>
            <p>Checking your login status...</p>
          </header>
        </div>
      </div>
    );
  }

  return (
    <div className="ai-demo-page">
      <div className="ai-demo-shell">
        <header className="ai-demo-header">
          <span className="ai-demo-badge">AI Demo</span>
          <h1>Learning Assistance Chatbot</h1>
          <p>
            This demo runs through the platform gateway and the shared AI service.
            Ask a short learning question and inspect the response flow.
          </p>
        </header>

        <div className="ai-demo-layout">
          <section className="ai-demo-main">
            <section className="ai-demo-chatbox" aria-live="polite">
              {messages.length === 0 ? (
                <div className="ai-demo-empty">
                  Start the conversation with a study question, concept explanation, or quick summary request.
                </div>
              ) : (
                messages.map((entry) => (
                  <article
                    key={entry.id}
                    className={`ai-demo-message ai-demo-message-${entry.role}`}
                  >
                    <span className="ai-demo-role">
                      {entry.role === "user" ? "You" : "Assistant"}
                    </span>
                    <p>{entry.text}</p>
                  </article>
                ))
              )}
            </section>

            <form className="ai-demo-composer" onSubmit={handleSubmit}>
              <div className="ai-demo-context-grid">
                <label className="ai-demo-field">
                  <span>Course context</span>
                  <input
                    type="text"
                    value={courseUuid ? "Attached from current course" : "No course context"}
                    disabled
                    readOnly
                  />
                </label>
                <label className="ai-demo-field">
                  <span>Module context</span>
                  <input
                    type="text"
                    value={moduleUuid ? "Attached from current module" : "No module context"}
                    disabled
                    readOnly
                  />
                </label>
              </div>
              <p className="ai-demo-session">
                {sessionUuidState ? "Current session loaded." : "A new session will be created on first send."}
              </p>
              <label className="ai-demo-label" htmlFor="ai-demo-message">
                Message
              </label>
              <textarea
                id="ai-demo-message"
                value={message}
                placeholder="Explain recursion simply, compare REST and GraphQL, or summarise Newton's laws."
                onChange={(event) => setMessage(event.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
              />
              <div className="ai-demo-actions">
                <p className="ai-demo-status">{status}</p>
                <button type="submit" disabled={loading || sessionDetailLoading}>
                  {loading ? "Sending..." : "Send"}
                </button>
              </div>
            </form>
          </section>

          <aside className="ai-demo-history">
            <div className="ai-demo-history-header">
              <h2>Session History</h2>
              <div className="ai-demo-history-actions">
                <button
                  type="button"
                  onClick={resetCurrentSession}
                  disabled={!sessionUuidState}
                >
                  New Chat
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const accessToken = localStorage.getItem("accessToken");
                    if (!accessToken) {
                      clearSessionState();
                      navigate("/", { replace: true });
                      return;
                    }

                    void fetchSessions(accessToken).catch((error) => {
                      setStatus(
                        error instanceof Error
                          ? `Failed to refresh sessions: ${error.message}`
                          : "Failed to refresh sessions."
                      );
                    });
                  }}
                  disabled={sessionsLoading}
                >
                  {sessionsLoading ? "Refreshing..." : "Refresh"}
                </button>
              </div>
            </div>
            <div className="ai-demo-history-list">
              {sessions.length === 0 ? (
                <p className="ai-demo-history-empty">No sessions yet.</p>
              ) : (
                sessions.map((entry) => (
                  <button
                    key={entry.session_uuid}
                    type="button"
                    className={`ai-demo-history-item${
                      entry.session_uuid === sessionUuidState ? " ai-demo-history-item-active" : ""
                    }`}
                    onClick={() => {
                      const accessToken = localStorage.getItem("accessToken");
                      if (!accessToken) {
                        clearSessionState();
                        navigate("/", { replace: true });
                        return;
                      }

                      void loadSessionDetail(entry.session_uuid, accessToken).catch((error) => {
                        setStatus(
                          error instanceof Error
                            ? `Failed to load session: ${error.message}`
                            : "Failed to load session."
                        );
                      });
                    }}
                    disabled={sessionDetailLoading}
                  >
                    <strong>{entry.title || "Session"}</strong>
                    <span>Messages: {entry.message_count}</span>
                    <span>
                      Context: {entry.course_uuid ? "Course" : "-"} / {entry.module_uuid ? "Module" : "-"}
                    </span>
                    <p>{entry.summary_text || "No summary yet."}</p>
                  </button>
                ))
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default AiDemo;
