from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationRecipientWrite(BaseModel):
    recipientUserUuid: str
    recipientEmail: str = Field(..., min_length=1, max_length=255)
    recipientName: str = Field(..., min_length=1, max_length=255)


class NotificationCreateRequest(BaseModel):
    notificationType: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    targetType: str | None = Field(default=None, max_length=100)
    targetId: str | None = Field(default=None, max_length=191)
    metadataJson: dict[str, Any] | None = None
    recipients: list[NotificationRecipientWrite] = Field(..., min_length=1)


class SystemNotificationRecipientWrite(BaseModel):
    recipientUserId: int = Field(..., ge=1)
    recipientEmail: str | None = Field(default=None, max_length=255)
    recipientName: str | None = Field(default=None, max_length=255)


class SystemNotificationCreateRequest(BaseModel):
    notificationType: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    targetType: str | None = Field(default=None, max_length=100)
    targetId: str | None = Field(default=None, max_length=191)
    metadataJson: dict[str, Any] | None = None
    dedupeKey: str | None = Field(default=None, min_length=1, max_length=255)
    recipients: list[SystemNotificationRecipientWrite] = Field(..., min_length=1)


class NotificationUpdateRequest(BaseModel):
    notificationType: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1)
    targetType: str | None = Field(default=None, max_length=100)
    targetId: str | None = Field(default=None, max_length=191)
    metadataJson: dict[str, Any] | None = None


class NotificationRead(BaseModel):
    notificationId: int
    notificationUuid: str
    actorUserId: int | None
    actorUserUuid: str | None
    actorEmail: str | None
    actorName: str | None
    notificationType: str
    title: str
    body: str
    targetType: str | None
    targetId: str | None
    metadataJson: dict[str, Any] | None
    createdAt: datetime
    updatedAt: datetime


class PaginatedNotificationResponse(BaseModel):
    items: list[NotificationRead]
    page: int
    pageSize: int
    total: int
    totalPages: int


class NotificationRecipientRead(NotificationRead):
    recipientUserId: int
    recipientUserUuid: str
    recipientEmail: str
    recipientName: str
    isRead: bool
    readAt: datetime | None
    isHidden: bool
    hiddenAt: datetime | None
    receivedAt: datetime


class PaginatedNotificationRecipientResponse(BaseModel):
    items: list[NotificationRecipientRead]
    page: int
    pageSize: int
    total: int
    totalPages: int


class NotificationUnreadCountResponse(BaseModel):
    recipientUserId: int
    recipientUserUuid: str
    unreadCount: int


class NotificationRecipientStateResponse(BaseModel):
    notificationId: int
    notificationUuid: str
    recipientUserId: int
    recipientUserUuid: str
    isRead: bool
    readAt: datetime | None
    isHidden: bool
    hiddenAt: datetime | None


class MarkAllNotificationsReadResponse(BaseModel):
    recipientUserId: int
    recipientUserUuid: str
    updatedCount: int
