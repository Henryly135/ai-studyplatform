export interface NotificationRecipientWrite {
  recipientUserUuid: string;
  recipientEmail: string;
  recipientName: string;
}

export interface NotificationCreateRequest {
  notificationType: string;
  title: string;
  body: string;
  targetType?: string | null;
  targetId?: string | null;
  metadataJson?: Record<string, unknown> | null;
  recipients: NotificationRecipientWrite[];
}

export interface NotificationUpdateRequest {
  notificationType?: string;
  title?: string;
  body?: string;
  targetType?: string | null;
  targetId?: string | null;
  metadataJson?: Record<string, unknown> | null;
}

export interface NotificationRead {
  notificationId: number;
  notificationUuid: string;
  actorUserId: number | null;
  actorUserUuid: string | null;
  actorEmail: string | null;
  actorName: string | null;
  notificationType: string;
  title: string;
  body: string;
  targetType: string | null;
  targetId: string | null;
  metadataJson: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface PaginatedNotificationResponse {
  items: NotificationRead[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface NotificationRecipientRead extends NotificationRead {
  recipientUserId: number;
  recipientUserUuid: string;
  recipientEmail: string;
  recipientName: string;
  isRead: boolean;
  readAt: string | null;
  isHidden: boolean;
  hiddenAt: string | null;
  receivedAt: string;
}

export interface PaginatedNotificationRecipientResponse {
  items: NotificationRecipientRead[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface NotificationUnreadCountResponse {
  recipientUserId: number;
  recipientUserUuid: string;
  unreadCount: number;
}

export interface NotificationRecipientStateResponse {
  notificationId: number;
  notificationUuid: string;
  recipientUserId: number;
  recipientUserUuid: string;
  isRead: boolean;
  readAt: string | null;
  isHidden: boolean;
  hiddenAt: string | null;
}

export interface MarkAllNotificationsReadResponse {
  recipientUserId: number;
  recipientUserUuid: string;
  updatedCount: number;
}

export interface NotificationRecipientListParams {
  includeHidden?: boolean;
  unreadOnly?: boolean;
  notificationType?: string;
  page?: number;
  pageSize?: number;
}

export interface NotificationListParams {
  notificationType?: string;
  page?: number;
  pageSize?: number;
}
