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
  NotificationCreateRequest,
  NotificationRead,
  NotificationRecipientRead,
  NotificationUpdateRequest,
} from "../../types/notification";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";

type NotificationsPageProps = {
  mode: "recipient" | "admin";
  currentUser: CurrentUserResponse;
};

type NotificationComposerState = {
  notificationType: string;
  title: string;
  body: string;
  targetType: string;
  targetId: string;
  metadataJson: string;
};

const PAGE_SIZE = 12;
const PAGE_POLL_INTERVAL_MS = 15000;

const INITIAL_COMPOSER_STATE: NotificationComposerState = {
  notificationType: "",
  title: "",
  body: "",
  targetType: "",
  targetId: "",
  metadataJson: "",
};

function formatDateTime(value: string | null) {
  if (!value) return "Not available";

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
  if (differenceMinutes < 1) return "Just now";
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
      : "Open",
  };
}

function isRecipientNotification(
  item: NotificationRead | NotificationRecipientRead
): item is NotificationRecipientRead {
  return "isRead" in item;
}

function buildNotificationPayload(
  composer: NotificationComposerState,
  recipients: AdminUserResponse[]
): NotificationCreateRequest | NotificationUpdateRequest {
  const metadataJson = composer.metadataJson.trim()
    ? (JSON.parse(composer.metadataJson) as Record<string, unknown>)
    : null;

  const basePayload = {
    notificationType: composer.notificationType.trim(),
    title: composer.title.trim(),
    body: composer.body.trim(),
    targetType: composer.targetType.trim() || null,
    targetId: composer.targetId.trim() || null,
    metadataJson,
  };

  if (recipients.length === 0) {
    return basePayload;
  }

  return {
    ...basePayload,
    recipients: recipients.map((recipient) => ({
      recipientUserUuid: recipient.userUuid,
      recipientEmail: recipient.email,
      recipientName: recipient.userName,
    })),
  };
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
  if (!open) return null;

  const selectedRecipientUuids = new Set(recipients.map((item) => item.userUuid));

  return (
    <div className="notifications-modal-backdrop" onClick={onClose}>
      <div className="notifications-modal" onClick={(event) => event.stopPropagation()}>
        <div className="notifications-modal-header">
          <div>
            <span className="notifications-panel-kicker">
              {mode === "create" ? "Create notification" : "Edit notification"}
            </span>
            <h2>{mode === "create" ? "New Notification" : "Update Notification"}</h2>
          </div>
          <button
            type="button"
            className="notifications-modal-close"
            onClick={onClose}
            aria-label="Close notification modal"
          >
            <LuX size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="notifications-modal-body">
          <div className="notifications-form-grid">
            <label className="notifications-field notifications-field-full">
              <span>Notification type</span>
              <input
                type="text"
                value={composer.notificationType}
                onChange={(event) =>
                  onComposerChange("notificationType", event.target.value)
                }
                placeholder="e.g. educator_approval_request_created"
              />
            </label>

            <label className="notifications-field notifications-field-full">
              <span>Title</span>
              <input
                type="text"
                value={composer.title}
                onChange={(event) => onComposerChange("title", event.target.value)}
                placeholder="Notification title"
              />
            </label>

            <label className="notifications-field notifications-field-full">
              <span>Body</span>
              <textarea
                value={composer.body}
                onChange={(event) => onComposerChange("body", event.target.value)}
                placeholder="Write the notification content shown to users."
              />
            </label>

            <label className="notifications-field">
              <span>Target type</span>
              <input
                type="text"
                value={composer.targetType}
                onChange={(event) => onComposerChange("targetType", event.target.value)}
                placeholder="Optional target type"
              />
            </label>

            <label className="notifications-field">
              <span>Target id</span>
              <input
                type="text"
                value={composer.targetId}
                onChange={(event) => onComposerChange("targetId", event.target.value)}
                placeholder="Optional target identifier"
              />
            </label>

            <label className="notifications-field notifications-field-full">
              <span>Metadata JSON</span>
              <textarea
                value={composer.metadataJson}
                onChange={(event) => onComposerChange("metadataJson", event.target.value)}
                placeholder='Optional JSON, e.g. { "courseUuid": "..." }'
              />
            </label>
          </div>

          {mode === "create" ? (
            <section className="notifications-recipient-picker">
              <div className="notifications-recipient-picker-header">
                <div>
                  <h3>Recipients</h3>
                  <p>Select one or more users who should receive this notification.</p>
                </div>
                <span className="notifications-pill-count">{recipients.length} selected</span>
              </div>

              <label className="notifications-recipient-search">
                <LuSearch size={16} aria-hidden="true" />
                <input
                  type="text"
                  value={recipientSearch}
                  onChange={(event) => onRecipientSearchChange(event.target.value)}
                  placeholder="Search users by name or email"
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
              <h3>Recipients</h3>
              <p>
                Recipient membership is fixed after creation. This edit form updates the
                notification content only.
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
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="notifications-primary-button"
            onClick={onSubmit}
            disabled={submitting}
          >
            {submitting
              ? mode === "create"
                ? "Creating..."
                : "Saving..."
              : mode === "create"
                ? "Create notification"
                : "Save changes"}
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

  const updateRecipientItemState = useCallback(
    (
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
    },
    []
  );

  useEffect(() => {
    let cancelled = false;

    const loadNotifications = async () => {
      if (!accessToken) {
        setErrorMessage("Missing access token. Please log in again.");
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

          setSelectedNotificationUuid((current) =>
            current || notificationsData.items[0]?.notificationUuid || current
          );
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

          setSelectedNotificationUuid((current) =>
            current || notificationsData.items[0]?.notificationUuid || current
          );
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error ? error.message : "Failed to load notifications."
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
  }, [
    accessToken,
    isAdminMode,
    page,
    refreshUnreadCount,
    showHidden,
    typeFilter,
    unreadOnly,
  ]);

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
    updateRecipientItemState,
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
        error instanceof Error ? error.message : "Failed to mark all notifications as read."
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
        setSuccessMessage("Notification marked as read.");
      } else if (action === "unread") {
        lastAutoReadNotificationUuidRef.current = item.notificationUuid;
        await markNotificationUnread(accessToken, item.notificationUuid);
        updateRecipientItemState(item.notificationUuid, (current) => ({
          ...current,
          isRead: false,
          readAt: null,
        }));
        setSuccessMessage("Notification marked as unread.");
      } else if (action === "hide") {
        await hideNotification(accessToken, item.notificationUuid);
        updateRecipientItemState(item.notificationUuid, (current) => ({
          ...current,
          isHidden: true,
          hiddenAt: new Date().toISOString(),
        }));
        setSuccessMessage("Notification hidden.");
      } else {
        await restoreNotification(accessToken, item.notificationUuid);
        updateRecipientItemState(item.notificationUuid, (current) => ({
          ...current,
          isHidden: false,
          hiddenAt: null,
        }));
        setSuccessMessage("Notification restored.");
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
    setComposerMode("create");
    setComposerState(INITIAL_COMPOSER_STATE);
    setSelectedRecipients([]);
    setRecipientSearch("");
    setComposerError("");
    setComposerOpen(true);
  };

  const openEditModal = () => {
    if (!activeAdminDetail) return;

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
      const payload = buildNotificationPayload(
        composerState,
        isCreateMode ? selectedRecipients : []
      );

      if (isCreateMode) {
        const createdNotification = await createNotification(
          accessToken,
          payload as NotificationCreateRequest
        );
        setAdminItems((current) => [createdNotification, ...current]);
        setSelectedNotificationUuid(createdNotification.notificationUuid);
        setSelectedAdminDetail(createdNotification);
        setNotificationTypes((current) =>
          Array.from(new Set([...current, createdNotification.notificationType])).sort()
        );
        emitAppRefresh({ scope: "notifications" });
        setSuccessMessage("Notification created successfully.");
      } else if (activeAdminDetail) {
        const updatedNotification = await updateNotification(
          accessToken,
          activeAdminDetail.notificationUuid,
          payload as NotificationUpdateRequest
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
        setSuccessMessage("Notification updated successfully.");
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
      setSuccessMessage("Notification deleted.");
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
          label: "Visible notifications",
          value: total,
          icon: <LuBell size={18} aria-hidden="true" />,
        },
        {
          label: "Notification types",
          value: notificationTypes.length,
          icon: <LuInbox size={18} aria-hidden="true" />,
        },
        {
          label: "Available recipients",
          value: recipientUsers.length,
          icon: <LuUsers size={18} aria-hidden="true" />,
        },
      ]
    : [
        {
          label: "Unread notifications",
          value: unreadCount,
          icon: <LuBellRing size={18} aria-hidden="true" />,
        },
        {
          label: "Loaded this page",
          value: visibleRecipientItems.length,
          icon: <LuInbox size={18} aria-hidden="true" />,
        },
        {
          label: "Hidden view",
          value: showHidden ? "On" : "Off",
          icon: <LuEyeOff size={18} aria-hidden="true" />,
        },
      ];

  if (!isAdminMode) {
    return (
      <section className="notifications-page notifications-page-recipient">
        {successMessage ? (
          <div className="notifications-toast" role="status" aria-live="polite">
            <strong>Success</strong>
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
              <LuMailCheck size={16} aria-hidden="true" />
              Mark all as read
            </button>
          </header>

          <section className="notifications-recipient-board">
            <div className="notifications-recipient-titlebar">
              <p>{unreadCount} unread updates waiting for you.</p>
            </div>

            {loading ? (
              <p className="notifications-feedback">Loading notifications...</p>
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
                      <strong>No notifications yet</strong>
                      <span>New course and platform updates will appear here.</span>
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
                    <p className="notifications-feedback">Loading details...</p>
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
                        <p className="notifications-recipient-greeting">Hi {currentUser.userName},</p>
                        <p>{activeRecipientDetail.body}</p>

                        <div className="notifications-recipient-summary">
                          <span>
                            From{" "}
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
                            {activeRecipientDetail.isRead ? "Mark unread" : "Mark read"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="notifications-empty-detail">
                      <LuBell size={18} aria-hidden="true" />
                      <strong>Select a notification</strong>
                      <span>Choose an item on the left to read the full message.</span>
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
          <strong>Success</strong>
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
                  <option value="">All types</option>
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
                    >
                      Unread only
                    </button>
                    <button
                      type="button"
                      className={`notifications-toggle${showHidden ? " notifications-toggle-active" : ""}`}
                      onClick={() => {
                        setShowHidden((current) => !current);
                        setPage(1);
                      }}
                    >
                      Show hidden
                    </button>
                    <button
                      type="button"
                      className="notifications-primary-button"
                      onClick={() => void handleMarkAllRead()}
                      disabled={submitting || unreadCount === 0}
                    >
                      <LuMailCheck size={16} aria-hidden="true" />
                      Mark all read
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="notifications-primary-button"
                    onClick={openCreateModal}
                  >
                    <LuPlus size={16} aria-hidden="true" />
                    New notification
                  </button>
                )}
              </div>
            </div>

            {loading ? (
              <p className="notifications-feedback">Loading notifications...</p>
            ) : null}

            {!loading && errorMessage ? (
              <p className="notifications-feedback notifications-feedback-error">
                {errorMessage}
              </p>
            ) : null}

            {!loading && !errorMessage ? (
              <>
                <div className="notifications-list-meta">
                  <span>
                    Showing{" "}
                    {isAdminMode ? visibleAdminItems.length : visibleRecipientItems.length} of {total}
                  </span>
                  <span>
                    Page {page} of {totalPages}
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
                      <strong>No notifications found</strong>
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
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="notifications-secondary-button"
                    onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                    disabled={page >= totalPages}
                  >
                    Next
                  </button>
                </div>
              </>
            ) : null}
          </section>

          <aside className="notifications-detail-panel">
            {detailLoading ? (
              <p className="notifications-feedback">Loading details...</p>
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
                        aria-label="Edit notification"
                      >
                        <LuPencil size={16} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="notifications-icon-button notifications-icon-button-danger"
                        onClick={() => void handleDeleteNotification()}
                        aria-label="Delete notification"
                        disabled={submitting}
                      >
                        <LuTrash2 size={16} aria-hidden="true" />
                      </button>
                    </div>
                  </div>

                  <dl className="notifications-detail-grid">
                    <div>
                      <dt>Actor</dt>
                      <dd>{activeAdminDetail.actorName ?? activeAdminDetail.actorEmail ?? "System"}</dd>
                    </div>
                    <div>
                      <dt>Created</dt>
                      <dd>{formatDateTime(activeAdminDetail.createdAt)}</dd>
                    </div>
                    <div>
                      <dt>Updated</dt>
                      <dd>{formatDateTime(activeAdminDetail.updatedAt)}</dd>
                    </div>
                    <div>
                      <dt>Target</dt>
                      <dd>
                        {activeAdminDetail.targetType
                          ? `${activeAdminDetail.targetType}${activeAdminDetail.targetId ? ` • ${activeAdminDetail.targetId}` : ""}`
                          : "General"}
                      </dd>
                    </div>
                  </dl>

                  <section className="notifications-detail-section">
                    <h3>Metadata</h3>
                    <pre>
                      {toMetadataText(activeAdminDetail.metadataJson) || "No metadata attached."}
                    </pre>
                  </section>
                </div>
              ) : (
                <div className="notifications-empty-detail">
                  <LuBell size={18} aria-hidden="true" />
                  <strong>Select a notification</strong>
                  <span>Choose an item from the left to inspect its content and metadata.</span>
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
                    <dt>From</dt>
                    <dd>{activeRecipientDetail.actorName ?? activeRecipientDetail.actorEmail ?? "System"}</dd>
                  </div>
                  <div>
                    <dt>Received</dt>
                    <dd>{formatDateTime(activeRecipientDetail.receivedAt)}</dd>
                  </div>
                  <div>
                    <dt>Status</dt>
                    <dd>{activeRecipientDetail.isRead ? "Read" : "Unread"}</dd>
                  </div>
                  <div>
                    <dt>Target</dt>
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
                        <LuMailOpen size={16} aria-hidden="true" />
                        Mark unread
                      </>
                    ) : (
                      <>
                        <LuMailCheck size={16} aria-hidden="true" />
                        Mark read
                      </>
                    )}
                  </button>
                </div>

                <section className="notifications-detail-section">
                  <h3>Metadata</h3>
                  <pre>
                    {toMetadataText(activeRecipientDetail.metadataJson) || "No metadata attached."}
                  </pre>
                </section>
              </div>
            ) : (
              <div className="notifications-empty-detail">
                <LuBell size={18} aria-hidden="true" />
                <strong>Select a notification</strong>
                <span>Choose an item from the left to read the full message.</span>
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
