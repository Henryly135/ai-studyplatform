import ReactMarkdown from "react-markdown";
import { LuMessageCircle, LuPlus } from "react-icons/lu";
import remarkGfm from "remark-gfm";

import type { ChatSessionDetail, ChatSessionSummary } from "../../types/chat";
import { LearnerAiQuestionPanel, type LearnerAiQuestionOption } from "./LearnerAiQuestionPanel";

type HomeAiConversationPanelProps = {
  title: string;
  sessionCountLabel: string;
  sessions: ChatSessionSummary[];
  sessionsLoading: boolean;
  sessionsError: string | null;
  activeSession: ChatSessionDetail | null;
  detailLoading: boolean;
  detailErrorMessage: string | null;
  sessionContextLabel: (session: ChatSessionSummary) => string;
  activeSessionContextLabel: string;
  courses: LearnerAiQuestionOption[];
  modules: LearnerAiQuestionOption[];
  models: LearnerAiQuestionOption[];
  selectedCourseUuid: string;
  selectedModuleUuid: string;
  selectedModelId: string;
  question: string;
  status: string;
  isSending: boolean;
  onCourseChange: (value: string) => void;
  onModuleChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
  onOpenSession: (sessionUuid: string) => void;
  onStartNewConversation: () => void;
};

function formatSessionTimestamp(value: string | null) {
  if (!value) {
    return "暂无活动";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return "最近";
  }

  return new Intl.DateTimeFormat("en-AU", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp);
}

export function HomeAiConversationPanel({
  title,
  sessionCountLabel,
  sessions,
  sessionsLoading,
  sessionsError,
  activeSession,
  detailLoading,
  detailErrorMessage,
  sessionContextLabel,
  activeSessionContextLabel,
  courses,
  modules,
  models,
  selectedCourseUuid,
  selectedModuleUuid,
  selectedModelId,
  question,
  status,
  isSending,
  onCourseChange,
  onModuleChange,
  onModelChange,
  onQuestionChange,
  onSubmit,
  onOpenSession,
  onStartNewConversation,
}: HomeAiConversationPanelProps) {
  return (
    <article className="home-ai-panel home-ai-conversation-panel">
      <div className="home-ai-panel-heading">
        <div className="home-ai-conversation-title">
          <LuMessageCircle size={20} aria-hidden="true" />
          <h2>{title}</h2>
        </div>
        <span>{sessionCountLabel}</span>
      </div>

      <div className="home-ai-conversation-layout">
        <aside className="home-ai-session-pane" aria-label="历史会话">
          <div className="home-ai-session-pane-heading">
            <strong>历史会话</strong>
            <button
              type="button"
              className="home-ai-new-session-button"
              onClick={onStartNewConversation}
              disabled={isSending}
            >
              <LuPlus size={15} aria-hidden="true" />
              <span>新建</span>
            </button>
          </div>

          {sessionsLoading ? <p className="home-ai-muted">正在加载会话...</p> : null}
          {sessionsError ? <p className="home-ai-muted">{sessionsError}</p> : null}
          {!sessionsLoading && !sessionsError && sessions.length === 0 ? (
            <p className="home-ai-muted">暂无历史会话，先新建一个问题吧。</p>
          ) : null}

          <div className="home-ai-session-list">
            {sessions.map((session) => (
              <button
                key={session.session_uuid}
                type="button"
                className={`home-ai-session-card ${
                  activeSession?.session.session_uuid === session.session_uuid
                    ? "home-ai-session-card-active"
                    : ""
                }`}
                onClick={() => onOpenSession(session.session_uuid)}
                disabled={detailLoading && activeSession?.session.session_uuid === session.session_uuid}
              >
                <div className="home-ai-session-meta">
                  <strong>{session.title || "未命名会话"}</strong>
                  <span>{formatSessionTimestamp(session.last_message_at)}</span>
                </div>
                <p className="home-ai-session-context">{sessionContextLabel(session)}</p>
              </button>
            ))}
          </div>
        </aside>

        <section className="home-ai-conversation-pane" aria-label="当前对话">
          {activeSession ? (
            <div className="home-ai-panel-heading home-ai-detail-heading">
              <div className="home-ai-detail-meta">
                <h2>{activeSession.session.title || "未命名会话"}</h2>
                <span>
                  {activeSessionContextLabel} · {formatSessionTimestamp(activeSession.session.last_message_at)}
                </span>
              </div>
              <span className="home-ai-session-state">继续当前会话</span>
            </div>
          ) : (
            <div className="home-ai-chat-empty">
              <strong>选择历史会话继续，或新建一个课程问题</strong>
              <span>打开历史会话后，输入框会固定在对话底部，并沿用原会话上下文。</span>
            </div>
          )}

          <div className="home-ai-detail-body">
            {detailLoading ? <p className="home-ai-muted">正在加载对话...</p> : null}
            {detailErrorMessage ? <p className="home-ai-muted">{detailErrorMessage}</p> : null}
            {!detailLoading && !detailErrorMessage && activeSession?.messages.length === 0 ? (
              <p className="home-ai-muted">该会话中没有消息。</p>
            ) : null}

            {!detailLoading && !detailErrorMessage && activeSession?.messages.length ? (
              <div className="home-ai-message-list">
                {activeSession.messages.map((message) => (
                  <article
                    key={message.message_id}
                    className={`home-ai-message home-ai-message-${
                      message.role === "user" ? "user" : "assistant"
                    }`}
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

          <LearnerAiQuestionPanel
            courses={courses}
            modules={modules}
            models={models}
            selectedCourseUuid={selectedCourseUuid}
            selectedModuleUuid={selectedModuleUuid}
            selectedModelId={selectedModelId}
            question={question}
            status={status}
            isSending={isSending}
            activeSessionUuid={activeSession?.session.session_uuid ?? null}
            activeSessionContext={activeSessionContextLabel}
            onCourseChange={onCourseChange}
            onModuleChange={onModuleChange}
            onModelChange={onModelChange}
            onQuestionChange={onQuestionChange}
            onSubmit={onSubmit}
            onStartNewConversation={onStartNewConversation}
          />
        </section>
      </div>
    </article>
  );
}
