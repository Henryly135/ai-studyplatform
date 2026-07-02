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

function asRecord(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
}

function toFiniteNumber(value: unknown, fallback: number, minimum?: number) {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : fallback;

  if (!Number.isFinite(parsed)) {
    return fallback;
  }

  return minimum === undefined ? parsed : Math.max(minimum, parsed);
}

function toNullableFiniteNumber(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : Number.NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function toNullableString(value: unknown) {
  return value === null || value === undefined ? null : String(value);
}

function toBoolean(value: unknown, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes"].includes(normalized)) {
      return true;
    }
    if (["false", "0", "no"].includes(normalized)) {
      return false;
    }
  }

  return fallback;
}

function normalizeMetadata(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function normalizeNotification(payload: unknown): NotificationRead {
  const data = asRecord(payload);

  return {
    notificationId: toFiniteNumber(data.notificationId, 0, 0),
    notificationUuid: String(data.notificationUuid ?? ""),
    actorUserId: toNullableFiniteNumber(data.actorUserId),
    actorUserUuid: toNullableString(data.actorUserUuid),
    actorEmail: toNullableString(data.actorEmail),
    actorName: toNullableString(data.actorName),
    notificationType: String(data.notificationType ?? ""),
    title: String(data.title ?? ""),
    body: String(data.body ?? ""),
    targetType: toNullableString(data.targetType),
    targetId: toNullableString(data.targetId),
    metadataJson: normalizeMetadata(data.metadataJson),
    createdAt: String(data.createdAt ?? ""),
    updatedAt: String(data.updatedAt ?? ""),
  };
}

function normalizeRecipientNotification(payload: unknown): NotificationRecipientRead {
  const data = asRecord(payload);

  return {
    ...normalizeNotification(data),
    recipientUserId: toFiniteNumber(data.recipientUserId, 0, 0),
    recipientUserUuid: String(data.recipientUserUuid ?? ""),
    recipientEmail: String(data.recipientEmail ?? ""),
    recipientName: String(data.recipientName ?? ""),
    isRead: toBoolean(data.isRead),
    readAt: toNullableString(data.readAt),
    isHidden: toBoolean(data.isHidden),
    hiddenAt: toNullableString(data.hiddenAt),
    receivedAt: String(data.receivedAt ?? ""),
  };
}

function normalizePaginatedNotifications(payload: unknown): PaginatedNotificationResponse {
  const data = asRecord(payload);
  const items = Array.isArray(data.items) ? data.items.map(normalizeNotification) : [];
  const page = toFiniteNumber(data.page, 1, 1);
  const pageSize = toFiniteNumber(data.pageSize, 20, 1);
  const total = toFiniteNumber(data.total, items.length, 0);

  return {
    items,
    page,
    pageSize,
    total,
    totalPages: toFiniteNumber(data.totalPages, Math.max(1, Math.ceil(total / pageSize)), 1),
  };
}

function normalizePaginatedRecipientNotifications(
  payload: unknown
): PaginatedNotificationRecipientResponse {
  const data = asRecord(payload);
  const items = Array.isArray(data.items) ? data.items.map(normalizeRecipientNotification) : [];
  const page = toFiniteNumber(data.page, 1, 1);
  const pageSize = toFiniteNumber(data.pageSize, 20, 1);
  const total = toFiniteNumber(data.total, items.length, 0);

  return {
    items,
    page,
    pageSize,
    total,
    totalPages: toFiniteNumber(data.totalPages, Math.max(1, Math.ceil(total / pageSize)), 1),
  };
}

function normalizeUnreadCount(payload: unknown): NotificationUnreadCountResponse {
  const data = asRecord(payload);

  return {
    recipientUserId: toFiniteNumber(data.recipientUserId, 0, 0),
    recipientUserUuid: String(data.recipientUserUuid ?? ""),
    unreadCount: toFiniteNumber(data.unreadCount, 0, 0),
  };
}

function normalizeRecipientState(payload: unknown): NotificationRecipientStateResponse {
  const data = asRecord(payload);

  return {
    notificationId: toFiniteNumber(data.notificationId, 0, 0),
    notificationUuid: String(data.notificationUuid ?? ""),
    recipientUserId: toFiniteNumber(data.recipientUserId, 0, 0),
    recipientUserUuid: String(data.recipientUserUuid ?? ""),
    isRead: toBoolean(data.isRead),
    readAt: toNullableString(data.readAt),
    isHidden: toBoolean(data.isHidden),
    hiddenAt: toNullableString(data.hiddenAt),
  };
}

function normalizeMarkAllRead(payload: unknown): MarkAllNotificationsReadResponse {
  const data = asRecord(payload);

  return {
    recipientUserId: toFiniteNumber(data.recipientUserId, 0, 0),
    recipientUserUuid: String(data.recipientUserUuid ?? ""),
    updatedCount: toFiniteNumber(data.updatedCount, 0, 0),
  };
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
    throw new Error(getErrorMessage(data, "获取通知失败。"));
  }

  return normalizePaginatedRecipientNotifications(data);
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
    throw new Error(getErrorMessage(data, "获取未读数量失败。"));
  }

  return normalizeUnreadCount(data);
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
    throw new Error(getErrorMessage(data, "全部标为已读失败。"));
  }

  return normalizeMarkAllRead(data);
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

  return normalizeRecipientState(data);
}

export async function markNotificationRead(accessToken: string, notificationUuid: string) {
  void accessToken;
  return updateRecipientNotificationState(
    `/me/notifications/${notificationUuid}/read`,
    "标记通知为已读失败。"
  );
}

export async function markNotificationUnread(accessToken: string, notificationUuid: string) {
  void accessToken;
  return updateRecipientNotificationState(
    `/me/notifications/${notificationUuid}/unread`,
    "标记通知为未读失败。"
  );
}

export async function hideNotification(accessToken: string, notificationUuid: string) {
  void accessToken;
  return updateRecipientNotificationState(
    `/me/notifications/${notificationUuid}`,
    "隐藏通知失败。"
  );
}

export async function restoreNotification(accessToken: string, notificationUuid: string) {
  void accessToken;
  return updateRecipientNotificationState(
    `/me/notifications/${notificationUuid}/restore`,
    "恢复通知失败。"
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
    throw new Error(getErrorMessage(data, "获取通知详情失败。"));
  }

  return normalizeRecipientNotification(data);
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
    throw new Error(getErrorMessage(data, "获取通知管理数据失败。"));
  }

  return normalizePaginatedNotifications(data);
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
    throw new Error(getErrorMessage(data, "获取通知详情失败。"));
  }

  return normalizeNotification(data);
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
    throw new Error(getErrorMessage(data, "创建通知失败。"));
  }

  return normalizeNotification(data);
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
    throw new Error(getErrorMessage(data, "更新通知失败。"));
  }

  return normalizeNotification(data);
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
    throw new Error(getErrorMessage(data, "删除通知失败。"));
  }
}
