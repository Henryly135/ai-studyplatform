import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { LuArrowLeft, LuArrowUp, LuX } from "react-icons/lu";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { getAiModelCatalog, getChatSessionDetail, listModuleChatSessions, sendChatMessage } from "../../services/chat";
import type {
  AiModelCatalog,
  CourseChatMessage,
  ChatSessionSummary,
} from "../../types/chat";
import {
  formatRagOptionSuffix,
  formatRagStatusText,
  isChatModelSelectable,
  resolveChatModelSelection,
} from "./courseChatModels";
import {
  runScopedCourseChatLoad,
  runScopedCourseChatSend,
} from "./courseChatAsyncScope";

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
    return "新会话";
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
  const [modelCatalog, setModelCatalog] = useState<AiModelCatalog | null>(null);
  const [modelCatalogError, setModelCatalogError] = useState<string | null>(null);
  const [modelCatalogScopeKey, setModelCatalogScopeKey] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState("");
  const messageViewportRef = useRef<HTMLDivElement | null>(null);
  const currentAsyncScopeToken = useMemo(
    () => Symbol(`${courseUuid}:${moduleUuid}:${isOpen ? "open" : "closed"}`),
    [courseUuid, isOpen, moduleUuid]
  );
  const activeAsyncScopeTokenRef = useRef(currentAsyncScopeToken);
  const isViewingSession = activeSessionUuid !== null;
  const currentModelCatalogScopeKey = `${courseUuid}:${moduleUuid}`;
  const activeModelCatalog =
    modelCatalogScopeKey === currentModelCatalogScopeKey ? modelCatalog : null;
  const activeModelCatalogError =
    modelCatalogScopeKey === currentModelCatalogScopeKey ? modelCatalogError : null;

  useLayoutEffect(() => {
    activeAsyncScopeTokenRef.current = currentAsyncScopeToken;
    return () => {
      if (activeAsyncScopeTokenRef.current === currentAsyncScopeToken) {
        activeAsyncScopeTokenRef.current = Symbol("disposed-course-chat-scope");
      }
    };
  }, [currentAsyncScopeToken]);

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
    if (!isOpen) {
      return;
    }

    let cancelled = false;
    const requestedScopeKey = `${courseUuid}:${moduleUuid}`;
    setModelCatalog(null);
    setModelCatalogError(null);
    setModelCatalogScopeKey(null);
    setSelectedModelId("");

    void getAiModelCatalog({ courseUuid, moduleUuid })
      .then((catalog) => {
        if (cancelled) {
          return;
        }

        setModelCatalog(catalog);
        setModelCatalogError(null);
        setModelCatalogScopeKey(requestedScopeKey);
        setSelectedModelId((current) => resolveChatModelSelection(catalog, current));
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setModelCatalog(null);
        setSelectedModelId("");
        setModelCatalogError(error instanceof Error ? error.message : "模型目录加载失败。");
        setModelCatalogScopeKey(requestedScopeKey);
      });

    return () => {
      cancelled = true;
    };
  }, [courseUuid, isOpen, moduleUuid]);

  useEffect(() => {
    setSessions([]);
    setActiveSessionUuid(null);
    setMessages([]);
    setComposerValue("");
    setIsLoadingSessionDetail(false);
    setIsSending(false);
    if (isOpen) {
      setStatus("选择一个会话，或发送新消息开始另一个会话。");
    }
  }, [courseUuid, moduleUuid, isOpen]);

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
  const selectedModel = useMemo(
    () =>
      activeModelCatalog?.providers
        .flatMap((provider) => provider.models)
        .find((model) => model.modelId === selectedModelId) ?? null,
    [activeModelCatalog, selectedModelId]
  );
  const hasUsableSelectedModel = selectedModel
    ? isChatModelSelectable(selectedModel)
    : false;

  const loadSession = async (sessionUuid: string) => {
    const requestScopeToken = currentAsyncScopeToken;
    setIsLoadingSessionDetail(true);
    setStatus("正在加载会话...");

    await runScopedCourseChatLoad({
      load: () => getChatSessionDetail(sessionUuid),
      isCurrent: () => activeAsyncScopeTokenRef.current === requestScopeToken,
      onSuccess: (detail) => {
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
      },
      onError: (error) => {
        setStatus(error instanceof Error ? error.message : "所选会话加载失败。");
      },
      onSettled: () => {
        setIsLoadingSessionDetail(false);
      },
    });
  };

  const handleSend = async () => {
    const requestScopeToken = currentAsyncScopeToken;
    const trimmedMessage = composerValue.trim();
    if (
      !trimmedMessage ||
      isSending ||
      isLoadingSessionDetail ||
      !hasUsableSelectedModel
    ) {
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

    await runScopedCourseChatSend({
      send: () =>
        sendChatMessage({
          courseUuid,
          moduleUuid,
          message: trimmedMessage,
          sessionUuid: activeSessionUuid,
          modelId: selectedModelId,
        }),
      refresh: () => listModuleChatSessions(moduleUuid),
      isCurrent: () => activeAsyncScopeTokenRef.current === requestScopeToken,
      onSuccess: (response, updatedSessions) => {
        setSessions(updatedSessions);
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
      },
      onError: (error) => {
        setStatus(error instanceof Error ? error.message : "消息发送失败。");
        if (wasViewingSession) {
          setMessages((current) => current.slice(0, -1));
        } else {
          setActiveSessionUuid(null);
          setMessages([]);
        }
        setComposerValue(trimmedMessage);
      },
      onSettled: () => {
        setIsSending(false);
      },
    });
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
            <label className="course-chat-model-picker">
              <span>模型</span>
              <select
                value={selectedModelId}
                onChange={(event) => setSelectedModelId(event.target.value)}
                disabled={isSending || !activeModelCatalog}
              >
                {!activeModelCatalog ? <option value="">默认模型</option> : null}
                {activeModelCatalog?.providers.map((provider) => (
                  <optgroup key={provider.provider} label={provider.label || provider.provider}>
                    {provider.models
                      .filter((model) => model.capabilities.includes("chat"))
                      .map((model) => (
                        <option
                          key={model.modelId}
                          value={model.modelId}
                          disabled={!isChatModelSelectable(model)}
                        >
                          {model.name}
                          {model.modelId === activeModelCatalog.userSelectedModelId ? " (已选)" : ""}
                          {model.isDefault || model.modelId === activeModelCatalog.defaultModelId ? " (默认)" : ""}
                          {formatRagOptionSuffix(model)}
                          {!model.available && model.unavailableReason ? ` - ${model.unavailableReason}` : ""}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
              {selectedModel ? (
                <small
                  className={`course-chat-model-pair${
                    selectedModel.ragReady === false ? " course-chat-model-pair-warning" : ""
                  }`}
                  aria-live="polite"
                >
                  向量模型：
                  {selectedModel.pairedEmbeddingModelName ||
                    selectedModel.pairedEmbeddingModelId ||
                    "待模型目录同步"}
                  {selectedModel.embeddingDimension
                    ? ` · ${selectedModel.embeddingDimension} 维`
                    : ""}
                  <span>{formatRagStatusText(selectedModel)}</span>
                </small>
              ) : null}
              {activeModelCatalogError ? <small>{activeModelCatalogError}</small> : null}
            </label>
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
                placeholder={
                  hasUsableSelectedModel
                    ? "询问这个模块..."
                    : activeModelCatalogError
                      ? "模型目录不可用，暂时无法发送"
                      : !activeModelCatalog
                        ? "正在准备可用模型..."
                        : selectedModel
                          ? "当前模型暂不可用"
                          : "当前没有可用模型"
                }
                disabled={isSending || !hasUsableSelectedModel}
              />
              <button
                type="submit"
                className="course-chat-send"
                disabled={!composerValue.trim() || isSending || !hasUsableSelectedModel}
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
