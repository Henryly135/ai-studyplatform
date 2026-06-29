import type { ApiErrorResponse } from "../types/auth";
import type {
  MarkAllNotificationsReadResponse,
  NotificationCreateRequest,
  NotificationListParams,
  NotificationRead,
  NotificationRecipientListParams,
  NotificationRecipientRead,
  NotificationRecipientStateResponse,
  NotificationUnreadCountResponse,
  NotificationUpdateRequest,
  PaginatedNotificationRecipientResponse,
  PaginatedNotificationResponse,
} from "../types/notification";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const API_BASE_URL = `${(import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "")}/communication`;

async function parseJsonSafe(response: Response) {
  return parseJsonText(await response.text());
}

function getErrorMessage(data: ApiErrorResponse | null, fallback: string) {
  if (!data) return fallback;

  if (data.errors && data.errors.length > 0) {
    return data.errors.map((item) => `${item.field}: ${item.reason}`).join(", ");
  }

  return data.detail || fallback;
}

function buildQueryString(params: Record<string, string | number | boolean | undefined>) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === "" || value === false) {
      return;
    }

    searchParams.set(key, String(value));
  });

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

export async function listMyNotifications(
  accessToken: string,
  params: NotificationRecipientListParams = {}
): Promise<PaginatedNotificationRecipientResponse> {
  void accessToken;

  const query = buildQueryString({
    includeHidden: params.includeHidden,
    unreadOnly: params.unreadOnly,
    notificationType: params.notificationType,
    page: params.page ?? 1,
    pageSize: params.pageSize ?? 20,
  });

  const response = await fetch(`${API_BASE_URL}/me/notifications${query}`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to fetch notifications."));
  }

  return data as PaginatedNotificationRecipientResponse;
}

export async function getNotificationUnreadCount(
  accessToken: string
): Promise<NotificationUnreadCountResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/me/notifications/unread-count`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to fetch unread count."));
  }

  return data as NotificationUnreadCountResponse;
}

export async function markAllNotificationsRead(
  accessToken: string
): Promise<MarkAllNotificationsReadResponse> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/me/notifications/read-all`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to mark all notifications as read."));
  }

  return data as MarkAllNotificationsReadResponse;
}

async function updateRecipientNotificationState(
  path: string,
  fallback: string
): Promise<NotificationRecipientStateResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: path.endsWith("/read") || path.endsWith("/unread") || path.endsWith("/restore")
      ? "PATCH"
      : "DELETE",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, fallback));
  }

  return data as NotificationRecipientStateResponse;
}

export async function markNotificationRead(accessToken: string, notificationUuid: string) {
  void accessToken;
  return updateRecipientNotificationState(
    `/me/notifications/${notificationUuid}/read`,
    "Failed to mark notification as read."
  );
}

export async function markNotificationUnread(accessToken: string, notificationUuid: string) {
  void accessToken;
  return updateRecipientNotificationState(
    `/me/notifications/${notificationUuid}/unread`,
    "Failed to mark notification as unread."
  );
}

export async function hideNotification(accessToken: string, notificationUuid: string) {
  void accessToken;
  return updateRecipientNotificationState(
    `/me/notifications/${notificationUuid}`,
    "Failed to hide notification."
  );
}

export async function restoreNotification(accessToken: string, notificationUuid: string) {
  void accessToken;
  return updateRecipientNotificationState(
    `/me/notifications/${notificationUuid}/restore`,
    "Failed to restore notification."
  );
}

export async function getMyNotification(
  accessToken: string,
  notificationUuid: string
): Promise<NotificationRecipientRead> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/me/notifications/${notificationUuid}`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to fetch notification details."));
  }

  return data as NotificationRecipientRead;
}

export async function listNotifications(
  accessToken: string,
  params: NotificationListParams = {}
): Promise<PaginatedNotificationResponse> {
  void accessToken;

  const query = buildQueryString({
    notificationType: params.notificationType,
    page: params.page ?? 1,
    pageSize: params.pageSize ?? 20,
  });

  const response = await fetch(`${API_BASE_URL}/notifications${query}`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to fetch notification management data."));
  }

  return data as PaginatedNotificationResponse;
}

export async function getNotification(
  accessToken: string,
  notificationUuid: string
): Promise<NotificationRead> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/notifications/${notificationUuid}`, {
    method: "GET",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to fetch notification details."));
  }

  return data as NotificationRead;
}

export async function createNotification(
  accessToken: string,
  payload: NotificationCreateRequest
): Promise<NotificationRead> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/notifications`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to create notification."));
  }

  return data as NotificationRead;
}

export async function updateNotification(
  accessToken: string,
  notificationUuid: string,
  payload: NotificationUpdateRequest
): Promise<NotificationRead> {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/notifications/${notificationUuid}`, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Failed to update notification."));
  }

  return data as NotificationRead;
}

export async function deleteNotification(accessToken: string, notificationUuid: string) {
  void accessToken;

  const response = await fetch(`${API_BASE_URL}/notifications/${notificationUuid}`, {
    method: "DELETE",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
  });

  const data = await parseJsonSafe(response);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok && response.status !== 204) {
    throw new Error(getErrorMessage(data, "Failed to delete notification."));
  }
}
