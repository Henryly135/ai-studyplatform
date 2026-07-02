import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  LuBell,
  LuBellRing,
  LuEyeOff,
  LuInbox,
  LuMailCheck,
  LuMailOpen,
  LuPencil,
  LuPlus,
  LuSearch,
  LuTrash2,
  LuUsers,
  LuX,
} from "react-icons/lu";

import "./NotificationsPage.css";
import { getAdminUsers } from "../../services/admin";
import {
  createNotification,
  deleteNotification,
  getMyNotification,
  getNotification,
  getNotificationUnreadCount,
  hideNotification,
  listMyNotifications,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  markNotificationUnread,
  restoreNotification,
  updateNotification,
} from "../../services/notification";
import type { CurrentUserResponse } from "../../types/auth";
import type { AdminUserResponse } from "../../types/admin";
import type {
  NotificationRead,
  NotificationRecipientRead,
} from "../../types/notification";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";
import {
  INITIAL_COMPOSER_STATE,
  buildNotificationCreatePayload,
  buildNotificationUpdatePayload,
  type NotificationComposerState,
} from "./notificationComposer";

type NotificationsPageProps = {
  mode: "recipient" | "admin";
  currentUser: CurrentUserResponse;
};

const PAGE_SIZE = 12;
const PAGE_POLL_INTERVAL_MS = 15000;

function formatDateTime(value: string | null) {
  if (!value) return "不可用";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en-AU", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatNotificationType(value: string) {
  return value
    .split(/[._-]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatRelativeTime(value: string | null) {
  if (!value) return "Recently";

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;

  const differenceMinutes = Math.max(0, Math.floor((Date.now() - timestamp.getTime()) / 60000));
  if (differenceMinutes < 1) return "刚刚";
  if (differenceMinutes < 60) return `${differenceMinutes} minutes ago`;

  const differenceHours = Math.floor(differenceMinutes / 60);
  if (differenceHours < 24) {
    return `${differenceHours} hour${differenceHours === 1 ? "" : "s"} ago`;
  }

  const differenceDays = Math.floor(differenceHours / 24);
  return `${differenceDays} day${differenceDays === 1 ? "" : "s"} ago`;
}

function toMetadataText(metadataJson: Record<string, unknown> | null) {
  if (!metadataJson || Object.keys(metadataJson).length === 0) {
    return "";
  }

  return JSON.stringify(metadataJson, null, 2);
}

function getNotificationAction(metadataJson: Record<string, unknown> | null) {
  if (!metadataJson) return null;
  const frontendPath = metadataJson.frontendPath;
  if (typeof frontendPath !== "string" || !frontendPath.startsWith("/")) {
    return null;
  }
  const actionLabel = metadataJson.actionLabel;
  return {
    frontendPath,
    actionLabel: typeof actionLabel === "string" && actionLabel.trim()
      ? actionLabel
      : "打开",
  };
}

function isRecipientNotification(
  item: NotificationRead | NotificationRecipientRead
): item is NotificationRecipientRead {
  return "isRead" in item;
}

function NotificationComposerModal({
  mode,
  open,
  submitting,
  composer,
  recipients,
  recipientSearch,
  availableUsers,
  errorMessage,
  onClose,
  onComposerChange,
  onRecipientSearchChange,
  onToggleRecipient,
  onSubmit,
}: {
  mode: "create" | "edit";
  open: boolean;
  submitting: boolean;
  composer: NotificationComposerState;
  recipients: AdminUserResponse[];
  recipientSearch: string;
  availableUsers: AdminUserResponse[];
  errorMessage: string;
  onClose: () => void;
  onComposerChange: (field: keyof NotificationComposerState, value: string) => void;
  onRecipientSearchChange: (value: string) => void;
  onToggleRecipient: (user: AdminUserResponse) => void;
  onSubmit: () => void;
}) {
  const titleId = "notification-composer-title";
  const descriptionId = "notification-composer-description";
  const requestClose = useCallback(() => {
    if (!submitting) {
      onClose();
    }
  }, [onClose, submitting]);

  useEffect(() => {
    if (!open || submitting) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        requestClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, requestClose, submitting]);

  if (!open) return null;

  const selectedRecipientUuids = new Set(recipients.map((item) => item.userUuid));

  return (
    <div className="notifications-modal-backdrop" onClick={requestClose}>
      <div
        className="notifications-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="notifications-modal-header">
          <div>
            <span className="notifications-panel-kicker">
              {mode === "create" ? "Create notification" : "编辑通知"}
            </span>
            <h2 id={titleId}>{mode === "create" ? "New Notification" : "Update Notification"}</h2>
            <p id={descriptionId} className="notifications-modal-description">
              {mode === "create"
                ? "Compose a platform notification and choose the users who should receive it."
                : "Update the notification content while keeping its recipient list unchanged."}
            </p>
          </div>
          <button
            type="button"
            className="notifications-modal-close"
            onClick={requestClose}
            disabled={submitting}
            aria-label="关闭通知窗口"
          >
            <LuX size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="notifications-modal-body">
          <div className="notifications-form-grid">
            <label className="notifications-field notifications-field-full">
              <span>通知类型</span>
              <input
                type="text"
                value={composer.notificationType}
                onChange={(event) =>
                  onComposerChange("notificationType", event.target.value)
                }
                placeholder="例如：教师审批请求"
                autoFocus
              />
            </label>

            <label className="notifications-field notifications-field-full">
              <span>标题</span>
              <input
                type="text"
                value={composer.title}
                onChange={(event) => onComposerChange("title", event.target.value)}
                placeholder="通知标题"
              />
            </label>

            <label className="notifications-field notifications-field-full">
              <span>正文</span>
              <textarea
                value={composer.body}
                onChange={(event) => onComposerChange("body", event.target.value)}
                placeholder="填写展示给用户的通知内容。"
              />
            </label>

            <label className="notifications-field">
              <span>目标类型</span>
              <input
                type="text"
                value={composer.targetType}
                onChange={(event) => onComposerChange("targetType", event.target.value)}
                placeholder="可选目标类型"
              />
            </label>

            <label className="notifications-field">
              <span>目标编号</span>
              <input
                type="text"
                value={composer.targetId}
                onChange={(event) => onComposerChange("targetId", event.target.value)}
                placeholder="可选目标标识符"
              />
            </label>

            <label className="notifications-field notifications-field-full">
              <span>元数据</span>
              <textarea
                value={composer.metadataJson}
                onChange={(event) => onComposerChange("metadataJson", event.target.value)}
                placeholder="可选：填写课程编号、模块编号或其他补充信息"
              />
            </label>
          </div>

          {mode === "create" ? (
            <section className="notifications-recipient-picker">
              <div className="notifications-recipient-picker-header">
                <div>
                  <h3>接收人</h3>
                  <p>选择一个或多个应接收该通知的用户。</p>
                </div>
                <span className="notifications-pill-count">{recipients.length}已选择</span>
              </div>

              <label className="notifications-recipient-search">
                <LuSearch size={16} aria-hidden="true" />
                <input
                  type="text"
                  value={recipientSearch}
                  onChange={(event) => onRecipientSearchChange(event.target.value)}
                  placeholder="按姓名或邮箱搜索用户"
                />
              </label>

              {recipients.length > 0 ? (
                <div className="notifications-recipient-chips">
                  {recipients.map((recipient) => (
                    <button
                      key={recipient.userUuid}
                      type="button"
                      className="notifications-recipient-chip"
                      onClick={() => onToggleRecipient(recipient)}
                    >
                      {recipient.userName}
                      <LuX size={14} aria-hidden="true" />
                    </button>
                  ))}
                </div>
              ) : null}

              <div className="notifications-recipient-list">
                {availableUsers.map((user) => {
                  const isSelected = selectedRecipientUuids.has(user.userUuid);

                  return (
                    <button
                      key={user.userUuid}
                      type="button"
                      className={`notifications-recipient-option${isSelected ? " notifications-recipient-option-selected" : ""}`}
                      onClick={() => onToggleRecipient(user)}
                    >
                      <div>
                        <strong>{user.userName}</strong>
                        <span>{user.email}</span>
                      </div>
                      <em>{user.identity}</em>
                    </button>
                  );
                })}
              </div>
            </section>
          ) : (
            <section className="notifications-modal-note">
              <h3>接收人</h3>
              <p>
                创建后接收人不可更改。此编辑表单仅更新通知内容。
              </p>
            </section>
          )}

          {errorMessage ? (
            <p className="notifications-feedback notifications-feedback-error">
              {errorMessage}
            </p>
          ) : null}
        </div>

        <div className="notifications-modal-actions">
          <button
            type="button"
            className="notifications-secondary-button"
            onClick={requestClose}
            disabled={submitting}
          >取消
          </button>
          <button
            type="button"
            className="notifications-primary-button"
            onClick={onSubmit}
            disabled={submitting}
          >
            {submitting
              ? mode === "create"
                ? "创建中..."
                : "保存中..."
              : mode === "create"
                ? "Create notification"
                : "保存修改"}
          </button>
        </div>
      </div>
    </div>
  );
}

function NotificationsPage({ mode, currentUser }: NotificationsPageProps) {
  const navigate = useNavigate();
  const [recipientItems, setRecipientItems] = useState<NotificationRecipientRead[]>([]);
  const [adminItems, setAdminItems] = useState<NotificationRead[]>([]);
  const [selectedNotificationUuid, setSelectedNotificationUuid] = useState<string | null>(null);
  const [selectedRecipientDetail, setSelectedRecipientDetail] =
    useState<NotificationRecipientRead | null>(null);
  const [selectedAdminDetail, setSelectedAdminDetail] = useState<NotificationRead | null>(
    null
  );
  const [notificationTypes, setNotificationTypes] = useState<string[]>([]);
  const [recipientUsers, setRecipientUsers] = useState<AdminUserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [detailError, setDetailError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [unreadCount, setUnreadCount] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [showHidden, setShowHidden] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerMode, setComposerMode] = useState<"create" | "edit">("create");
  const [composerState, setComposerState] =
    useState<NotificationComposerState>(INITIAL_COMPOSER_STATE);
  const [composerError, setComposerError] = useState("");
  const [recipientSearch, setRecipientSearch] = useState("");
  const [selectedRecipients, setSelectedRecipients] = useState<AdminUserResponse[]>([]);
  const detailRequestIdRef = useRef(0);
  const lastAutoReadNotificationUuidRef = useRef<string | null>(null);
  const autoReadRequestIdRef = useRef(0);
  const pollInFlightRef = useRef(false);
  const composerTriggerRef = useRef<HTMLElement | null>(null);

  const accessToken = localStorage.getItem("accessToken") ?? "";
  const isAdminMode = mode === "admin";
  const activeRecipientDetail =
    selectedRecipientDetail ??
    recipientItems.find((item) => item.notificationUuid === selectedNotificationUuid) ??
    null;
  const activeRecipientNotificationUuid = activeRecipientDetail?.notificationUuid ?? null;
  const activeRecipientIsRead = activeRecipientDetail?.isRead ?? true;
  const activeAdminDetail =
    selectedAdminDetail ??
    adminItems.find((item) => item.notificationUuid === selectedNotificationUuid) ??
    null;

  const visibleRecipientItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return recipientItems;

    return recipientItems.filter((item) =>
      [item.title, item.body, item.actorName ?? "", item.notificationType]
        .join(" ")
        .toLowerCase()
        .includes(keyword)
    );
  }, [recipientItems, search]);

  const visibleAdminItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return adminItems;

    return adminItems.filter((item) =>
      [item.title, item.body, item.actorName ?? "", item.notificationType]
        .join(" ")
        .toLowerCase()
        .includes(keyword)
    );
  }, [adminItems, search]);

  const filteredRecipientUsers = useMemo(() => {
    const keyword = recipientSearch.trim().toLowerCase();
    if (!keyword) return recipientUsers;

    return recipientUsers.filter((user) =>
      [user.userName, user.email, user.identity].join(" ").toLowerCase().includes(keyword)
    );
  }, [recipientUsers, recipientSearch]);

  const refreshUnreadCount = useCallback(async () => {
    if (isAdminMode || !accessToken) return;
    const countData = await getNotificationUnreadCount(accessToken);
    setUnreadCount(countData.unreadCount);
  }, [accessToken, isAdminMode]);

  useEffect(() => {
    let cancelled = false;

    const loadNotifications = async () => {
      if (!accessToken) {
        setErrorMessage("缺少访问令牌，请重新登录。");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setErrorMessage("");

        if (isAdminMode) {
          const [notificationsData, usersData] = await Promise.all([
            listNotifications(accessToken, {
              notificationType: typeFilter || undefined,
              page,
              pageSize: PAGE_SIZE,
            }),
            getAdminUsers(accessToken),
          ]);

          if (cancelled) return;

          setAdminItems(notificationsData.items);
          setTotalPages(Math.max(1, notificationsData.totalPages));
          setTotal(notificationsData.total);
          setRecipientUsers(usersData.users);
          setNotificationTypes((current) => {
            const next = new Set(current);
            notificationsData.items.forEach((item) => next.add(item.notificationType));
            return Array.from(next).sort();
          });

          if (!selectedNotificationUuid && notificationsData.items.length > 0) {
            setSelectedNotificationUuid(notificationsData.items[0].notificationUuid);
          }
        } else {
          const [notificationsData] = await Promise.all([
            listMyNotifications(accessToken, {
              includeHidden: showHidden,
              unreadOnly,
              notificationType: typeFilter || undefined,
              page,
              pageSize: PAGE_SIZE,
            }),
            refreshUnreadCount(),
          ]);

          if (cancelled) return;

          setRecipientItems(notificationsData.items);
          setTotalPages(Math.max(1, notificationsData.totalPages));
          setTotal(notificationsData.total);
          setNotificationTypes((current) => {
            const next = new Set(current);
            notificationsData.items.forEach((item) => next.add(item.notificationType));
            return Array.from(next).sort();
          });

          if (!selectedNotificationUuid && notificationsData.items.length > 0) {
            setSelectedNotificationUuid(notificationsData.items[0].notificationUuid);
          }
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error ? error.message : "通知加载失败。"
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadNotifications();

    return () => {
      cancelled = true;
    };
  }, [accessToken, isAdminMode, page, refreshUnreadCount, showHidden, typeFilter, unreadOnly, selectedNotificationUuid]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    const poll = async () => {
      if (pollInFlightRef.current) {
        return;
      }

      pollInFlightRef.current = true;
      try {
        if (isAdminMode) {
          const data = await listNotifications(accessToken, {
            notificationType: typeFilter || undefined,
            page,
            pageSize: PAGE_SIZE,
          });

          setAdminItems(data.items);
          setTotalPages(Math.max(1, data.totalPages));
          setTotal(data.total);
          setNotificationTypes((current) => {
            const next = new Set(current);
            data.items.forEach((item) => next.add(item.notificationType));
            return Array.from(next).sort();
          });
          return;
        }

        const [itemsData, countData] = await Promise.all([
          listMyNotifications(accessToken, {
            includeHidden: showHidden,
            unreadOnly,
            notificationType: typeFilter || undefined,
            page,
            pageSize: PAGE_SIZE,
          }),
          getNotificationUnreadCount(accessToken),
        ]);

        setRecipientItems(itemsData.items);
        setTotalPages(Math.max(1, itemsData.totalPages));
        setTotal(itemsData.total);
        setUnreadCount(countData.unreadCount);
        setNotificationTypes((current) => {
          const next = new Set(current);
          itemsData.items.forEach((item) => next.add(item.notificationType));
          return Array.from(next).sort();
        });
      } catch {
        // Keep polling silent; the existing page state already shows the last known data.
      } finally {
        pollInFlightRef.current = false;
      }
    };

    const interval = window.setInterval(() => {
      void poll();
    }, PAGE_POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [accessToken, isAdminMode, page, showHidden, typeFilter, unreadOnly]);

  useEffect(() => {
    return subscribeAppRefresh(["notifications"], () => {
      if (!accessToken) {
        return;
      }
      if (isAdminMode) {
        void listNotifications(accessToken, {
          notificationType: typeFilter || undefined,
          page,
          pageSize: PAGE_SIZE,
        }).then((data) => {
          setAdminItems(data.items);
          setTotalPages(Math.max(1, data.totalPages));
          setTotal(data.total);
        });
        return;
      }

      void Promise.all([
        listMyNotifications(accessToken, {
          includeHidden: showHidden,
          unreadOnly,
          notificationType: typeFilter || undefined,
          page,
          pageSize: PAGE_SIZE,
        }),
        getNotificationUnreadCount(accessToken),
      ]).then(([itemsData, countData]) => {
        setRecipientItems(itemsData.items);
        setTotalPages(Math.max(1, itemsData.totalPages));
        setTotal(itemsData.total);
        setUnreadCount(countData.unreadCount);
      });
    });
  }, [accessToken, isAdminMode, page, showHidden, typeFilter, unreadOnly]);

  useEffect(() => {
    if (!selectedNotificationUuid || !accessToken) return;

    let cancelled = false;
    const requestId = detailRequestIdRef.current + 1;
    detailRequestIdRef.current = requestId;

    const loadDetail = async () => {
      try {
        setDetailLoading(true);
        setDetailError("");

        if (isAdminMode) {
          const detail = await getNotification(accessToken, selectedNotificationUuid);
          if (!cancelled && detailRequestIdRef.current === requestId) {
            setSelectedAdminDetail(detail);
          }
        } else {
          const detail = await getMyNotification(accessToken, selectedNotificationUuid);
          if (!cancelled && detailRequestIdRef.current === requestId) {
            setSelectedRecipientDetail(detail);
          }
        }
      } catch (error) {
        if (!cancelled && detailRequestIdRef.current === requestId) {
          setDetailError(
            error instanceof Error
              ? error.message
              : "Failed to load notification details."
          );
        }
      } finally {
        if (!cancelled && detailRequestIdRef.current === requestId) {
          setDetailLoading(false);
        }
      }
    };

    void loadDetail();

    return () => {
      cancelled = true;
    };
  }, [accessToken, isAdminMode, selectedNotificationUuid]);

  useEffect(() => {
    if (
      isAdminMode ||
      !accessToken ||
      !activeRecipientNotificationUuid ||
      activeRecipientIsRead
    ) {
      return;
    }

    if (lastAutoReadNotificationUuidRef.current === activeRecipientNotificationUuid) {
      return;
    }

    lastAutoReadNotificationUuidRef.current = activeRecipientNotificationUuid;

    let cancelled = false;
    const requestId = autoReadRequestIdRef.current + 1;
    autoReadRequestIdRef.current = requestId;

    const markSelectedNotificationRead = async () => {
      try {
        const response = await markNotificationRead(accessToken, activeRecipientNotificationUuid);
        if (cancelled || autoReadRequestIdRef.current !== requestId) return;

        updateRecipientItemState(activeRecipientNotificationUuid, (current) => ({
          ...current,
          isRead: response.isRead,
          readAt: response.readAt,
        }));
        await refreshUnreadCount();
        emitAppRefresh({ scope: "notifications" });
      } catch {
        // Keep selection responsive even if the auto-read update fails.
      }
    };

    void markSelectedNotificationRead();

    return () => {
      cancelled = true;
    };
  }, [
    accessToken,
    activeRecipientIsRead,
    activeRecipientNotificationUuid,
    isAdminMode,
    refreshUnreadCount,
  ]);

  useEffect(() => {
    if (!successMessage) return;

    const timer = window.setTimeout(() => setSuccessMessage(""), 2200);
    return () => window.clearTimeout(timer);
  }, [successMessage]);

  const handleSelectNotification = async (
    notificationUuid: string,
    item?: NotificationRecipientRead
  ) => {
    if (selectedNotificationUuid !== notificationUuid) {
      lastAutoReadNotificationUuidRef.current = null;
      setSelectedNotificationUuid(notificationUuid);
      return;
    }

    if (isAdminMode || !accessToken || !item || item.isRead) {
      return;
    }

    autoReadRequestIdRef.current += 1;
    detailRequestIdRef.current += 1;

    try {
      const response = await markNotificationRead(accessToken, notificationUuid);
      updateRecipientItemState(notificationUuid, (current) => ({
        ...current,
        isRead: response.isRead,
        readAt: response.readAt,
      }));
      await refreshUnreadCount();
      emitAppRefresh({ scope: "notifications" });
    } catch {
      // Keep selection responsive even if the manual read update fails.
    }
  };

  const updateRecipientItemState = (
    notificationUuid: string,
    updater: (item: NotificationRecipientRead) => NotificationRecipientRead
  ) => {
    setRecipientItems((current) =>
      current.map((item) =>
        item.notificationUuid === notificationUuid ? updater(item) : item
      )
    );
    setSelectedRecipientDetail((current) =>
      current && current.notificationUuid === notificationUuid ? updater(current) : current
    );
  };

  const handleMarkAllRead = async () => {
    if (!accessToken) return;

    try {
      setSubmitting(true);
      const response = await markAllNotificationsRead(accessToken);
      setSuccessMessage(
        response.updatedCount > 0
          ? `${response.updatedCount} notifications marked as read.`
          : "All notifications were already read."
      );
      setRecipientItems((current) =>
        current.map((item) => ({
          ...item,
          isRead: true,
          readAt: item.readAt ?? new Date().toISOString(),
        }))
      );
      setSelectedRecipientDetail((current) =>
        current
          ? {
              ...current,
              isRead: true,
              readAt: current.readAt ?? new Date().toISOString(),
            }
          : current
      );
      await refreshUnreadCount();
      emitAppRefresh({ scope: "notifications" });
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "全部标记为已读失败。"
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecipientAction = async (
    action: "read" | "unread" | "hide" | "restore",
    item: NotificationRecipientRead
  ) => {
    if (!accessToken) return;

    try {
      setSubmitting(true);
      detailRequestIdRef.current += 1;
      autoReadRequestIdRef.current += 1;

      if (action === "read") {
        lastAutoReadNotificationUuidRef.current = item.notificationUuid;
        await markNotificationRead(accessToken, item.notificationUuid);
        updateRecipientItemState(item.notificationUuid, (current) => ({
          ...current,
          isRead: true,
          readAt: new Date().toISOString(),
        }));
        setSuccessMessage("通知已标记为已读。");
      } else if (action === "unread") {
        lastAutoReadNotificationUuidRef.current = item.notificationUuid;
        await markNotificationUnread(accessToken, item.notificationUuid);
        updateRecipientItemState(item.notificationUuid, (current) => ({
          ...current,
          isRead: false,
          readAt: null,
        }));
        setSuccessMessage("通知已标记为未读。");
      } else if (action === "hide") {
        await hideNotification(accessToken, item.notificationUuid);
        updateRecipientItemState(item.notificationUuid, (current) => ({
          ...current,
          isHidden: true,
          hiddenAt: new Date().toISOString(),
        }));
        setSuccessMessage("通知已隐藏。");
      } else {
        await restoreNotification(accessToken, item.notificationUuid);
        updateRecipientItemState(item.notificationUuid, (current) => ({
          ...current,
          isHidden: false,
          hiddenAt: null,
        }));
        setSuccessMessage("通知已恢复。");
      }

      await refreshUnreadCount();
      emitAppRefresh({ scope: "notifications" });
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to update notification state."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleNotificationNavigate = (path: string) => {
    if (path === "/home/ai/profile-init") {
      localStorage.setItem("postProfileInitRedirect", "/home/communication");
    }
    navigate(path);
  };

  const openCreateModal = () => {
    composerTriggerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setComposerMode("create");
    setComposerState(INITIAL_COMPOSER_STATE);
    setSelectedRecipients([]);
    setRecipientSearch("");
    setComposerError("");
    setComposerOpen(true);
  };

  const openEditModal = () => {
    if (!activeAdminDetail) return;

    composerTriggerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setComposerMode("edit");
    setComposerState({
      notificationType: activeAdminDetail.notificationType,
      title: activeAdminDetail.title,
      body: activeAdminDetail.body,
      targetType: activeAdminDetail.targetType ?? "",
      targetId: activeAdminDetail.targetId ?? "",
      metadataJson: toMetadataText(activeAdminDetail.metadataJson),
    });
    setSelectedRecipients([]);
    setRecipientSearch("");
    setComposerError("");
    setComposerOpen(true);
  };

  const closeComposer = () => {
    setComposerOpen(false);
    setComposerError("");
    setSelectedRecipients([]);
    setRecipientSearch("");
    setComposerState(INITIAL_COMPOSER_STATE);
    const trigger = composerTriggerRef.current;
    composerTriggerRef.current = null;
    if (trigger?.isConnected) {
      window.setTimeout(() => trigger.focus(), 0);
    }
  };

  const handleComposerChange = (
    field: keyof NotificationComposerState,
    value: string
  ) => {
    setComposerState((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const handleToggleRecipient = (user: AdminUserResponse) => {
    setSelectedRecipients((current) =>
      current.some((item) => item.userUuid === user.userUuid)
        ? current.filter((item) => item.userUuid !== user.userUuid)
        : [...current, user]
    );
  };

  const handleSubmitComposer = async () => {
    if (!accessToken) return;

    const isCreateMode = composerMode === "create";
    if (
      !composerState.notificationType.trim() ||
      !composerState.title.trim() ||
      !composerState.body.trim()
    ) {
      setComposerError("Notification type, title, and body are required.");
      return;
    }

    if (isCreateMode && selectedRecipients.length === 0) {
      setComposerError("Select at least one recipient.");
      return;
    }

    try {
      setSubmitting(true);
      setComposerError("");

      if (isCreateMode) {
        const payload = buildNotificationCreatePayload(composerState, selectedRecipients);
        const createdNotification = await createNotification(
          accessToken,
          payload
        );
        setAdminItems((current) => [createdNotification, ...current]);
        setSelectedNotificationUuid(createdNotification.notificationUuid);
        setSelectedAdminDetail(createdNotification);
        setNotificationTypes((current) =>
          Array.from(new Set([...current, createdNotification.notificationType])).sort()
        );
        emitAppRefresh({ scope: "notifications" });
        setSuccessMessage("通知创建成功。");
      } else if (activeAdminDetail) {
        const payload = buildNotificationUpdatePayload(composerState);
        const updatedNotification = await updateNotification(
          accessToken,
          activeAdminDetail.notificationUuid,
          payload
        );
        setAdminItems((current) =>
          current.map((item) =>
            item.notificationUuid === updatedNotification.notificationUuid
              ? updatedNotification
              : item
          )
        );
        setSelectedAdminDetail(updatedNotification);
        emitAppRefresh({ scope: "notifications" });
        setSuccessMessage("通知更新成功。");
      }

      closeComposer();
    } catch (error) {
      setComposerError(
        error instanceof Error ? error.message : "Failed to save notification."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteNotification = async () => {
    if (!accessToken || !activeAdminDetail) return;

    try {
      setSubmitting(true);
      const deletingUuid = activeAdminDetail.notificationUuid;
      await deleteNotification(accessToken, deletingUuid);
      const remainingItems = adminItems.filter(
        (item) => item.notificationUuid !== deletingUuid
      );
      setAdminItems(remainingItems);
      setSelectedAdminDetail(null);
      setSelectedNotificationUuid(remainingItems[0]?.notificationUuid ?? null);
      emitAppRefresh({ scope: "notifications" });
      setSuccessMessage("通知已删除。");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to delete notification."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const summaryCards = isAdminMode
    ? [
        {
          label: "可见通知",
          value: total,
          icon: <LuBell size={18} aria-hidden="true" />,
        },
        {
          label: "通知类型",
          value: notificationTypes.length,
          icon: <LuInbox size={18} aria-hidden="true" />,
        },
        {
          label: "可选接收人",
          value: recipientUsers.length,
          icon: <LuUsers size={18} aria-hidden="true" />,
        },
      ]
    : [
        {
          label: "未读通知",
          value: unreadCount,
          icon: <LuBellRing size={18} aria-hidden="true" />,
        },
        {
          label: "本页已加载",
          value: visibleRecipientItems.length,
          icon: <LuInbox size={18} aria-hidden="true" />,
        },
        {
          label: "隐藏视图",
          value: showHidden ? "On" : "Off",
          icon: <LuEyeOff size={18} aria-hidden="true" />,
        },
      ];

  if (!isAdminMode) {
    return (
      <section className="notifications-page notifications-page-recipient">
        {successMessage ? (
          <div className="notifications-toast" role="status" aria-live="polite">
            <strong>成功</strong>
            <span>{successMessage}</span>
          </div>
        ) : null}

        <div className="notifications-recipient-shell">
          <header className="notifications-recipient-header">
            <div className="notifications-recipient-profile">
              <div className="notifications-recipient-avatar">
                {currentUser.userName.charAt(0).toUpperCase()}
              </div>
              <div className="notifications-recipient-profile-copy">
                <h1>{currentUser.userName}</h1>
                <p>{currentUser.identity}</p>
              </div>
            </div>

            <button
              type="button"
              className="notifications-recipient-mark-all"
              onClick={() => void handleMarkAllRead()}
              disabled={submitting || unreadCount === 0}
            >
              <LuMailCheck size={16} aria-hidden="true" />全部标记为已读
            </button>
          </header>

          <section className="notifications-recipient-board">
            <div className="notifications-recipient-titlebar">
              <p>{unreadCount}条未读更新等待查看。</p>
            </div>

            {loading ? (
              <p className="notifications-feedback">正在加载通知...</p>
            ) : errorMessage ? (
              <p className="notifications-feedback notifications-feedback-error">
                {errorMessage}
              </p>
            ) : (
              <div className="notifications-recipient-grid">
                <aside className="notifications-recipient-list">
                  {recipientItems.length === 0 ? (
                    <div className="notifications-empty-state">
                      <LuInbox size={20} aria-hidden="true" />
                      <strong>暂无通知</strong>
                      <span>新的课程和平台更新会显示在这里。</span>
                    </div>
                  ) : (
                    recipientItems.map((item) => {
                      const isSelected = item.notificationUuid === selectedNotificationUuid;

                      return (
                        <button
                          key={item.notificationUuid}
                          type="button"
                          className={`notifications-recipient-list-item${isSelected ? " notifications-recipient-list-item-selected" : ""}${item.isRead ? "" : " notifications-recipient-list-item-unread"}`}
                          onClick={() => void handleSelectNotification(item.notificationUuid, item)}
                        >
                          <div className="notifications-recipient-list-item-icon">
                            <LuBell size={16} aria-hidden="true" />
                          </div>
                          <div className="notifications-recipient-list-item-copy">
                            <strong>{item.title}</strong>
                            <span>{formatRelativeTime(item.receivedAt)}</span>
                          </div>
                        </button>
                      );
                    })
                  )}
                </aside>

                <section className="notifications-recipient-detail">
                  {detailLoading ? (
                    <p className="notifications-feedback">正在加载详情...</p>
                  ) : detailError ? (
                    <p className="notifications-feedback notifications-feedback-error">
                      {detailError}
                    </p>
                  ) : activeRecipientDetail ? (
                    <div className="notifications-recipient-message">
                      <div className="notifications-recipient-message-header">
                        <div>
                          <span className="notifications-type-chip">
                            {formatNotificationType(activeRecipientDetail.notificationType)}
                          </span>
                          <h3>{activeRecipientDetail.title}</h3>
                          <p>{formatRelativeTime(activeRecipientDetail.receivedAt)}</p>
                        </div>
                      </div>

                      <div className="notifications-recipient-message-body">
                        <p className="notifications-recipient-greeting">你好 {currentUser.userName},</p>
                        <p>{activeRecipientDetail.body}</p>

                        <div className="notifications-recipient-summary">
                          <span>来自{" "}
                            <strong>
                              {activeRecipientDetail.actorName ??
                                activeRecipientDetail.actorEmail ??
                                "System"}
                            </strong>
                          </span>
                          <span>{formatDateTime(activeRecipientDetail.receivedAt)}</span>
                          <span>{activeRecipientDetail.isRead ? "Read" : "Unread"}</span>
                        </div>

                        {(() => {
                          const action = getNotificationAction(activeRecipientDetail.metadataJson);
                          return action ? (
                            <div className="notifications-recipient-primary-action">
                              <button
                                type="button"
                                className="notifications-primary-button"
                                onClick={() => handleNotificationNavigate(action.frontendPath)}
                              >
                                {action.actionLabel}
                              </button>
                            </div>
                          ) : null;
                        })()}

                        <div className="notifications-recipient-actions">
                          <button
                            type="button"
                            className="notifications-secondary-button"
                            onClick={() =>
                              void handleRecipientAction(
                                activeRecipientDetail.isRead ? "unread" : "read",
                                activeRecipientDetail
                              )
                            }
                            disabled={submitting}
                          >
                            {activeRecipientDetail.isRead ? "标为未读" : "标为已读"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="notifications-empty-detail">
                      <LuBell size={18} aria-hidden="true" />
                      <strong>选择一条通知</strong>
                      <span>选择左侧项目以阅读完整消息。</span>
                    </div>
                  )}
                </section>
              </div>
            )}
          </section>
        </div>
      </section>
    );
  }

  return (
    <section className="notifications-page">
      {successMessage ? (
        <div className="notifications-toast" role="status" aria-live="polite">
          <strong>成功</strong>
          <span>{successMessage}</span>
        </div>
      ) : null}

      <div className="notifications-shell">
        <section className="notifications-hero">
          <div className="notifications-hero-copy">
            <span className="notifications-panel-kicker">
              {isAdminMode ? "Notification Management" : "Notification"}
            </span>
            <h1>
              {isAdminMode ? "Manage platform notifications" : "Your notification inbox"}
            </h1>
            <p>
              {isAdminMode
                ? "Create, review, and maintain system notifications without changing the rest of the workspace flow."
                : `Keep up with course activity, approvals, and platform updates for ${currentUser.userName}.`}
            </p>
          </div>

          <div className="notifications-summary-grid">
            {summaryCards.map((card) => (
              <article key={card.label} className="notifications-summary-card">
                <div className="notifications-summary-icon">{card.icon}</div>
                <strong>{card.value}</strong>
                <span>{card.label}</span>
              </article>
            ))}
          </div>
        </section>

        <div className="notifications-workspace">
          <section className="notifications-list-panel">
            <div className="notifications-toolbar">
              <label className="notifications-search">
                <LuSearch size={16} aria-hidden="true" />
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={
                    isAdminMode
                      ? "Search notifications by title, body, or actor"
                      : "Search your notifications"
                  }
                />
              </label>

              <div className="notifications-toolbar-actions">
                <select
                  className="notifications-select"
                  value={typeFilter}
                  onChange={(event) => {
                    setTypeFilter(event.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">全部类型</option>
                  {notificationTypes.map((type) => (
                    <option key={type} value={type}>
                      {formatNotificationType(type)}
                    </option>
                  ))}
                </select>

                {!isAdminMode ? (
                  <>
                    <button
                      type="button"
                      className={`notifications-toggle${unreadOnly ? " notifications-toggle-active" : ""}`}
                      onClick={() => {
                        setUnreadOnly((current) => !current);
                        setPage(1);
                      }}
                    >仅未读
                    </button>
                    <button
                      type="button"
                      className={`notifications-toggle${showHidden ? " notifications-toggle-active" : ""}`}
                      onClick={() => {
                        setShowHidden((current) => !current);
                        setPage(1);
                      }}
                    >显示隐藏项
                    </button>
                    <button
                      type="button"
                      className="notifications-primary-button"
                      onClick={() => void handleMarkAllRead()}
                      disabled={submitting || unreadCount === 0}
                    >
                      <LuMailCheck size={16} aria-hidden="true" />全部标为已读
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="notifications-primary-button"
                    onClick={openCreateModal}
                  >
                    <LuPlus size={16} aria-hidden="true" />新建通知
                  </button>
                )}
              </div>
            </div>

            {loading ? (
              <p className="notifications-feedback">正在加载通知...</p>
            ) : null}

            {!loading && errorMessage ? (
              <p className="notifications-feedback notifications-feedback-error">
                {errorMessage}
              </p>
            ) : null}

            {!loading && !errorMessage ? (
              <>
                <div className="notifications-list-meta">
                  <span>显示{" "}
                    {isAdminMode ? visibleAdminItems.length : visibleRecipientItems.length}共 {total}
                  </span>
                  <span>页码 {page}共 {totalPages}
                  </span>
                </div>

                <div className="notifications-list">
                  {(isAdminMode ? visibleAdminItems : visibleRecipientItems).map((item) => {
                    const isSelected = item.notificationUuid === selectedNotificationUuid;
                    const isRecipientItem = isRecipientNotification(item);

                    return (
                      <button
                        key={item.notificationUuid}
                        type="button"
                        className={`notifications-list-item${isSelected ? " notifications-list-item-selected" : ""}${isRecipientItem && !item.isRead ? " notifications-list-item-unread" : ""}`}
                        onClick={() => handleSelectNotification(item.notificationUuid)}
                      >
                        <div className="notifications-list-item-top">
                          <span className="notifications-type-chip">
                            {formatNotificationType(item.notificationType)}
                          </span>
                          <time>
                            {formatDateTime(
                              isRecipientItem ? item.receivedAt : item.createdAt
                            )}
                          </time>
                        </div>
                        <strong>{item.title}</strong>
                        <p>{item.body}</p>
                        <div className="notifications-list-item-footer">
                          <span>{item.actorName ?? item.actorEmail ?? "System"}</span>
                          {isRecipientItem ? (
                            <em>{item.isHidden ? "Hidden" : item.isRead ? "Read" : "Unread"}</em>
                          ) : (
                            <em>{item.targetType ?? "General"}</em>
                          )}
                        </div>
                      </button>
                    );
                  })}

                  {(isAdminMode ? visibleAdminItems : visibleRecipientItems).length === 0 ? (
                    <div className="notifications-empty-state">
                      <LuInbox size={20} aria-hidden="true" />
                      <strong>未找到通知</strong>
                      <span>
                        {isAdminMode
                          ? "Try a different type filter or create a new notification."
                          : "Try a different filter or wait for new activity."}
                      </span>
                    </div>
                  ) : null}
                </div>

                <div className="notifications-pagination">
                  <button
                    type="button"
                    className="notifications-secondary-button"
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={page <= 1}
                  >上一页
                  </button>
                  <button
                    type="button"
                    className="notifications-secondary-button"
                    onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                    disabled={page >= totalPages}
                  >下一页
                  </button>
                </div>
              </>
            ) : null}
          </section>

          <aside className="notifications-detail-panel">
            {detailLoading ? (
              <p className="notifications-feedback">正在加载详情...</p>
            ) : detailError ? (
              <p className="notifications-feedback notifications-feedback-error">
                {detailError}
              </p>
            ) : isAdminMode ? (
              activeAdminDetail ? (
                <div className="notifications-detail">
                  <div className="notifications-detail-header">
                    <div>
                      <span className="notifications-type-chip">
                        {formatNotificationType(activeAdminDetail.notificationType)}
                      </span>
                      <h2>{activeAdminDetail.title}</h2>
                      <p>{activeAdminDetail.body}</p>
                    </div>
                    <div className="notifications-detail-actions">
                      <button
                        type="button"
                        className="notifications-icon-button"
                        onClick={openEditModal}
                        aria-label="编辑通知"
                      >
                        <LuPencil size={16} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="notifications-icon-button notifications-icon-button-danger"
                        onClick={() => void handleDeleteNotification()}
                        aria-label="删除通知"
                        disabled={submitting}
                      >
                        <LuTrash2 size={16} aria-hidden="true" />
                      </button>
                    </div>
                  </div>

                  <dl className="notifications-detail-grid">
                    <div>
                      <dt>操作者</dt>
                      <dd>{activeAdminDetail.actorName ?? activeAdminDetail.actorEmail ?? "System"}</dd>
                    </div>
                    <div>
                      <dt>创建时间</dt>
                      <dd>{formatDateTime(activeAdminDetail.createdAt)}</dd>
                    </div>
                    <div>
                      <dt>更新时间</dt>
                      <dd>{formatDateTime(activeAdminDetail.updatedAt)}</dd>
                    </div>
                    <div>
                      <dt>目标</dt>
                      <dd>
                        {activeAdminDetail.targetType
                          ? `${activeAdminDetail.targetType}${activeAdminDetail.targetId ? ` • ${activeAdminDetail.targetId}` : ""}`
                          : "General"}
                      </dd>
                    </div>
                  </dl>

                  <section className="notifications-detail-section">
                    <h3>元数据</h3>
                    <pre>
                      {toMetadataText(activeAdminDetail.metadataJson) || "未附加元数据。"}
                    </pre>
                  </section>
                </div>
              ) : (
                <div className="notifications-empty-detail">
                  <LuBell size={18} aria-hidden="true" />
                  <strong>选择一条通知</strong>
                  <span>选择左侧项目查看内容和元数据。</span>
                </div>
              )
            ) : activeRecipientDetail ? (
              <div className="notifications-detail">
                <div className="notifications-detail-header">
                  <div>
                    <span className="notifications-type-chip">
                      {formatNotificationType(activeRecipientDetail.notificationType)}
                    </span>
                    <h2>{activeRecipientDetail.title}</h2>
                    <p>{activeRecipientDetail.body}</p>
                  </div>
                </div>

                <dl className="notifications-detail-grid">
                  <div>
                    <dt>来自</dt>
                    <dd>{activeRecipientDetail.actorName ?? activeRecipientDetail.actorEmail ?? "System"}</dd>
                  </div>
                  <div>
                    <dt>接收时间</dt>
                    <dd>{formatDateTime(activeRecipientDetail.receivedAt)}</dd>
                  </div>
                  <div>
                    <dt>状态</dt>
                    <dd>{activeRecipientDetail.isRead ? "Read" : "Unread"}</dd>
                  </div>
                  <div>
                    <dt>目标</dt>
                    <dd>
                      {activeRecipientDetail.targetType
                        ? `${activeRecipientDetail.targetType}${activeRecipientDetail.targetId ? ` • ${activeRecipientDetail.targetId}` : ""}`
                        : "General"}
                    </dd>
                  </div>
                </dl>

                <div className="notifications-detail-actions-row">
                  {(() => {
                    const action = getNotificationAction(activeRecipientDetail.metadataJson);
                    return action ? (
                      <button
                        type="button"
                        className="notifications-primary-button"
                        onClick={() => handleNotificationNavigate(action.frontendPath)}
                      >
                        {action.actionLabel}
                      </button>
                    ) : null;
                  })()}
                  <button
                    type="button"
                    className="notifications-secondary-button"
                    onClick={() =>
                      void handleRecipientAction(
                        activeRecipientDetail.isRead ? "unread" : "read",
                        activeRecipientDetail
                      )
                    }
                    disabled={submitting}
                  >
                    {activeRecipientDetail.isRead ? (
                      <>
                        <LuMailOpen size={16} aria-hidden="true" />标为未读
                      </>
                    ) : (
                      <>
                        <LuMailCheck size={16} aria-hidden="true" />标为已读
                      </>
                    )}
                  </button>
                </div>

                <section className="notifications-detail-section">
                  <h3>元数据</h3>
                  <pre>
                    {toMetadataText(activeRecipientDetail.metadataJson) || "未附加元数据。"}
                  </pre>
                </section>
              </div>
            ) : (
              <div className="notifications-empty-detail">
                <LuBell size={18} aria-hidden="true" />
                <strong>选择一条通知</strong>
                <span>选择左侧项目阅读完整消息。</span>
              </div>
            )}
          </aside>
        </div>
      </div>

      <NotificationComposerModal
        mode={composerMode}
        open={composerOpen}
        submitting={submitting}
        composer={composerState}
        recipients={selectedRecipients}
        recipientSearch={recipientSearch}
        availableUsers={filteredRecipientUsers}
        errorMessage={composerError}
        onClose={closeComposer}
        onComposerChange={handleComposerChange}
        onRecipientSearchChange={setRecipientSearch}
        onToggleRecipient={handleToggleRecipient}
        onSubmit={() => void handleSubmitComposer()}
      />
    </section>
  );
}

export default NotificationsPage;
