import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LuBell, LuCheckCheck, LuChevronRight } from "react-icons/lu";

import {
  getNotificationUnreadCount,
  listMyNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../../services/notification";
import { getStoredAccessToken } from "../../services/api";
import type { NotificationRecipientRead } from "../../types/notification";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";
import "./HomeNotificationsMenu.css";

const MENU_PAGE_SIZE = 4;
const MENU_POLL_INTERVAL_MS = 15000;

function formatRelativeTime(value: string) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return "Recently";
  }

  const differenceMs = Date.now() - timestamp.getTime();
  const differenceMinutes = Math.max(0, Math.floor(differenceMs / 60000));

  if (differenceMinutes < 1) {
    return "刚刚";
  }

  if (differenceMinutes < 60) {
    return `${differenceMinutes}m ago`;
  }

  const differenceHours = Math.floor(differenceMinutes / 60);
  if (differenceHours < 24) {
    return `${differenceHours}h ago`;
  }

  const differenceDays = Math.floor(differenceHours / 24);
  if (differenceDays < 7) {
    return `${differenceDays}d ago`;
  }

  return new Intl.DateTimeFormat("en-AU", {
    month: "short",
    day: "numeric",
  }).format(timestamp);
}

function HomeNotificationsMenu() {
  const navigate = useNavigate();
  const menuRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [notifications, setNotifications] = useState<NotificationRecipientRead[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const pollInFlightRef = useRef(false);
  const closeMenu = useCallback((options?: { restoreFocus?: boolean }) => {
    setIsOpen(false);
    if (options?.restoreFocus === false) {
      return;
    }

    window.setTimeout(() => {
      triggerRef.current?.focus();
    }, 0);
  }, []);

  const loadUnreadCount = async () => {
    try {
      const accessToken = getStoredAccessToken();
      const unreadResponse = await getNotificationUnreadCount(accessToken);
      setUnreadCount(unreadResponse.unreadCount);
    } catch {
      setUnreadCount(0);
    }
  };

  const loadNotifications = async () => {
    setIsLoading(true);
    setErrorMessage("");

    try {
      const accessToken = getStoredAccessToken();
      const [notificationResponse, unreadResponse] = await Promise.all([
        listMyNotifications(accessToken, {
          page: 1,
          pageSize: MENU_PAGE_SIZE,
        }),
        getNotificationUnreadCount(accessToken),
      ]);

      setNotifications(notificationResponse.items);
      setUnreadCount(unreadResponse.unreadCount);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "通知加载失败。"
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadUnreadCount();
  }, []);

  useEffect(() => {
    const accessToken = getStoredAccessToken();
    if (!accessToken) {
      return;
    }

    const poll = async () => {
      if (pollInFlightRef.current) {
        return;
      }

      pollInFlightRef.current = true;
      try {
        if (isOpen) {
          await loadNotifications();
        } else {
          await loadUnreadCount();
        }
      } finally {
        pollInFlightRef.current = false;
      }
    };

    const interval = window.setInterval(() => {
      void poll();
    }, MENU_POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [isOpen]);

  useEffect(() => {
    return subscribeAppRefresh(["notifications"], () => {
      if (isOpen) {
        void loadNotifications();
      } else {
        void loadUnreadCount();
      }
    });
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        closeMenu({ restoreFocus: false });
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeMenu();
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeMenu, isOpen]);

  const handleToggle = () => {
    const nextOpen = !isOpen;
    setIsOpen(nextOpen);

    if (nextOpen) {
      void loadNotifications();
    }
  };

  const handleOpenNotificationCenter = () => {
    closeMenu({ restoreFocus: false });
    navigate("/home/communication");
  };

  const handleMarkAllRead = async () => {
    if (unreadCount < 1 || isMarkingAll) {
      return;
    }

    setIsMarkingAll(true);
    setErrorMessage("");

    try {
      const accessToken = getStoredAccessToken();
      await markAllNotificationsRead(accessToken);
      const readAt = new Date().toISOString();

      setNotifications((current) =>
        current.map((entry) => ({
          ...entry,
          isRead: true,
          readAt,
        }))
      );
      setUnreadCount(0);
      emitAppRefresh({ scope: "notifications" });
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "全部标记为已读失败。"
      );
    } finally {
      setIsMarkingAll(false);
    }
  };

  const handleOpenNotification = async (notification: NotificationRecipientRead) => {
    if (!notification.isRead) {
      try {
        const accessToken = getStoredAccessToken();
        const response = await markNotificationRead(accessToken, notification.notificationUuid);

        setNotifications((current) =>
          current.map((entry) =>
            entry.notificationUuid === notification.notificationUuid
              ? {
                  ...entry,
                  isRead: response.isRead,
                  readAt: response.readAt,
                }
              : entry
          )
        );
        setUnreadCount((current) => Math.max(0, current - 1));
        emitAppRefresh({ scope: "notifications" });
      } catch {
        // Keep navigation responsive even if the read receipt call fails.
      }
    }

    closeMenu({ restoreFocus: false });
    navigate("/home/communication");
  };

  return (
    <div className="home-notifications" ref={menuRef}>
      <button
        type="button"
        ref={triggerRef}
        className={`home-notifications-trigger${isOpen ? " home-notifications-trigger-open" : ""}`}
        onClick={handleToggle}
        aria-label="打开通知"
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-controls={isOpen ? "home-notifications-panel" : undefined}
      >
        <LuBell size={18} aria-hidden="true" />
        {unreadCount > 0 ? (
          <span className="home-notifications-badge" aria-label={`${unreadCount} unread notifications`}>
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>

      {isOpen ? (
        <div id="home-notifications-panel" className="home-notifications-panel" role="dialog" aria-label="通知">
          <div className="home-notifications-panel-header">
            <div>
              <h3>通知</h3>
            </div>

            <button
              type="button"
              className="home-notifications-mark-all"
              onClick={() => void handleMarkAllRead()}
              disabled={unreadCount < 1 || isMarkingAll}
            >
              <LuCheckCheck size={16} aria-hidden="true" />
              {isMarkingAll ? "标记中..." : "全部标记为已读"}
            </button>
          </div>

          {errorMessage ? (
            <p className="home-notifications-feedback home-notifications-feedback-error">
              {errorMessage}
            </p>
          ) : null}

          <div className="home-notifications-list">
            {isLoading ? (
              <p className="home-notifications-feedback">正在加载通知...</p>
            ) : notifications.length === 0 ? (
              <div className="home-notifications-empty">
                <strong>暂时没有新内容</strong>
                <p>平台发送的新通知会显示在这里。</p>
              </div>
            ) : (
              notifications.map((notification) => (
                <button
                  key={notification.notificationUuid}
                  type="button"
                  className={`home-notifications-item${notification.isRead ? "" : " home-notifications-item-unread"}`}
                  onClick={() => void handleOpenNotification(notification)}
                >
                  <div className="home-notifications-item-copy">
                    <strong>{notification.title}</strong>
                    <p>{notification.body}</p>
                  </div>
                  <div className="home-notifications-item-meta">
                    <span>{formatRelativeTime(notification.receivedAt)}</span>
                    <span className="home-notifications-item-link">查看通知
                      <LuChevronRight size={15} aria-hidden="true" />
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>

          <button
            type="button"
            className="home-notifications-footer"
            onClick={handleOpenNotificationCenter}
          >查看全部通知
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default HomeNotificationsMenu;
