from sqlalchemy.orm import Session

from app.core.uuid_codec import decode_user_uuid, encode_notification_uuid, encode_user_uuid
from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.repositories.notification_recipient_repository import NotificationRecipientRepository
from app.repositories.notification_repository import NotificationRepository, _UNSET
from app.schemas.notification import (
    MarkAllNotificationsReadResponse,
    NotificationCreateRequest,
    NotificationRead,
    NotificationRecipientRead,
    NotificationRecipientStateResponse,
    NotificationUnreadCountResponse,
    SystemNotificationCreateRequest,
    NotificationUpdateRequest,
    PaginatedNotificationRecipientResponse,
    PaginatedNotificationResponse,
)
from platform_common.errors import (
    invalid_identity_response_error,
    invalid_request_error,
    notification_not_found_error,
    notification_recipient_not_found_error,
)


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.notifications = NotificationRepository(session)
        self.recipients = NotificationRecipientRepository(session)

    def create_notification(self, *, payload: NotificationCreateRequest, current_user: dict) -> NotificationRead:
        recipient_rows = self._normalize_recipients(payload)
        notification = self.notifications.create(
            notification_type=self._normalize_required_text(payload.notificationType, field_name="notificationType"),
            title=self._normalize_required_text(payload.title, field_name="title"),
            body=self._normalize_required_text(payload.body, field_name="body"),
            actor_user_id=self._require_current_user_id(current_user),
            actor_email=self._normalize_optional_text(str(current_user.get("email"))),
            actor_name=self._normalize_optional_text(str(current_user.get("userName"))),
            target_type=self._normalize_optional_text(payload.targetType),
            target_id=self._normalize_optional_text(payload.targetId),
            metadata_json=payload.metadataJson,
        )
        self.recipients.create_many(notification_id=notification.notification_id, recipients=recipient_rows)
        self.session.commit()
        self.session.refresh(notification)
        return self._to_notification_read(notification)

    def create_system_notification(self, *, payload: SystemNotificationCreateRequest) -> NotificationRead:
        existing = self._find_existing_by_dedupe_key(payload)
        if existing is not None:
            return self._to_notification_read(existing)

        metadata_json = dict(payload.metadataJson or {})
        if payload.dedupeKey:
            metadata_json["dedupeKey"] = payload.dedupeKey

        notification = self.notifications.create(
            notification_type=self._normalize_required_text(payload.notificationType, field_name="notificationType"),
            title=self._normalize_required_text(payload.title, field_name="title"),
            body=self._normalize_required_text(payload.body, field_name="body"),
            actor_user_id=None,
            actor_email=None,
            actor_name="System",
            target_type=self._normalize_optional_text(payload.targetType),
            target_id=self._normalize_optional_text(payload.targetId),
            metadata_json=metadata_json or None,
        )
        self.recipients.create_many(
            notification_id=notification.notification_id,
            recipients=[
                {
                    "recipient_user_id": recipient.recipientUserId,
                    "recipient_email": self._normalize_optional_text(recipient.recipientEmail)
                    or f"user-{recipient.recipientUserId}@system.local",
                    "recipient_name": self._normalize_optional_text(recipient.recipientName)
                    or f"Learner {recipient.recipientUserId}",
                }
                for recipient in payload.recipients
            ],
        )
        self.session.commit()
        self.session.refresh(notification)
        return self._to_notification_read(notification)

    def list_all_notifications(
        self,
        *,
        notification_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedNotificationResponse:
        items, total, safe_page, total_pages = self.notifications.list_paginated(
            notification_type=self._normalize_optional_text(notification_type),
            page=page,
            page_size=page_size,
        )
        return PaginatedNotificationResponse(
            items=[self._to_notification_read(item) for item in items],
            page=safe_page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
        )

    def list_notifications(
        self,
        *,
        recipient_user_id: int,
        include_hidden: bool = False,
        unread_only: bool = False,
        notification_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedNotificationRecipientResponse:
        items, total, safe_page, total_pages = self.recipients.list_by_user(
            recipient_user_id=recipient_user_id,
            include_hidden=include_hidden,
            unread_only=unread_only,
            notification_type=self._normalize_optional_text(notification_type),
            page=page,
            page_size=page_size,
        )
        return PaginatedNotificationRecipientResponse(
            items=[self._to_recipient_read(item) for item in items],
            page=safe_page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
        )

    def get_notification(self, *, notification_id: int) -> NotificationRead:
        return self._to_notification_read(self._get_notification_or_404(notification_id))

    def update_notification(self, *, notification_id: int, payload: NotificationUpdateRequest) -> NotificationRead:
        notification = self._get_notification_or_404(notification_id)
        if self._is_update_payload_empty(payload):
            raise invalid_request_error("At least one field must be provided for update")

        updated = self.notifications.update(
            notification,
            notification_type=self._normalize_required_text(payload.notificationType, field_name="notificationType")
            if payload.notificationType is not None
            else _UNSET,
            title=self._normalize_required_text(payload.title, field_name="title") if payload.title is not None else _UNSET,
            body=self._normalize_required_text(payload.body, field_name="body") if payload.body is not None else _UNSET,
            target_type=self._normalize_optional_text(payload.targetType) if payload.targetType is not None else _UNSET,
            target_id=self._normalize_optional_text(payload.targetId) if payload.targetId is not None else _UNSET,
            metadata_json=payload.metadataJson if payload.metadataJson is not None else _UNSET,
        )
        self.session.commit()
        self.session.refresh(updated)
        return self._to_notification_read(updated)

    def delete_notification(self, *, notification_id: int) -> None:
        notification = self._get_notification_or_404(notification_id)
        self.notifications.delete(notification)
        self.session.commit()

    def get_recipient_notification(
        self,
        *,
        notification_id: int,
        recipient_user_id: int,
    ) -> NotificationRecipientRead:
        recipient = self._get_recipient_notification_or_404(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )
        return self._to_recipient_read(recipient)

    def count_unread_notifications(self, *, recipient_user_id: int) -> NotificationUnreadCountResponse:
        return NotificationUnreadCountResponse(
            recipientUserId=recipient_user_id,
            recipientUserUuid=encode_user_uuid(recipient_user_id),
            unreadCount=self.recipients.count_unread_by_user(recipient_user_id=recipient_user_id),
        )

    def mark_notification_read(
        self,
        *,
        notification_id: int,
        recipient_user_id: int,
        read_at,
    ) -> NotificationRecipientStateResponse:
        recipient = self._get_recipient_notification_or_404(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )
        updated = self.recipients.mark_read(recipient, read_at=read_at)
        self.session.commit()
        return self._to_state_response(updated)

    def mark_notification_unread(
        self,
        *,
        notification_id: int,
        recipient_user_id: int,
    ) -> NotificationRecipientStateResponse:
        recipient = self._get_recipient_notification_or_404(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )
        updated = self.recipients.mark_unread(recipient)
        self.session.commit()
        return self._to_state_response(updated)

    def mark_all_notifications_read(
        self,
        *,
        recipient_user_id: int,
        read_at,
    ) -> MarkAllNotificationsReadResponse:
        updated_count = self.recipients.mark_all_read(recipient_user_id=recipient_user_id, read_at=read_at)
        self.session.commit()
        return MarkAllNotificationsReadResponse(
            recipientUserId=recipient_user_id,
            recipientUserUuid=encode_user_uuid(recipient_user_id),
            updatedCount=updated_count,
        )

    def hide_notification(
        self,
        *,
        notification_id: int,
        recipient_user_id: int,
        hidden_at,
    ) -> NotificationRecipientStateResponse:
        recipient = self._get_recipient_notification_or_404(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )
        updated = self.recipients.hide(recipient, hidden_at=hidden_at)
        self.session.commit()
        return self._to_state_response(updated)

    def unhide_notification(
        self,
        *,
        notification_id: int,
        recipient_user_id: int,
    ) -> NotificationRecipientStateResponse:
        recipient = self._get_recipient_notification_or_404(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )
        updated = self.recipients.unhide(recipient)
        self.session.commit()
        return self._to_state_response(updated)

    def _require_current_user_id(self, current_user: dict) -> int:
        user_id = current_user.get("id")
        if not isinstance(user_id, int):
            raise invalid_identity_response_error()
        return user_id

    def _get_notification_or_404(self, notification_id: int) -> Notification:
        notification = self.notifications.get_by_id(notification_id)
        if notification is None:
            raise notification_not_found_error()
        return notification

    def _get_recipient_notification_or_404(
        self,
        *,
        notification_id: int,
        recipient_user_id: int,
    ) -> NotificationRecipient:
        recipient = self.recipients.get_by_notification_and_user(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )
        if recipient is None:
            raise notification_recipient_not_found_error()
        return recipient

    def _normalize_recipients(self, payload: NotificationCreateRequest) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        seen_user_ids: set[int] = set()
        for recipient in payload.recipients:
            recipient_user_id = decode_user_uuid(recipient.recipientUserUuid)
            if recipient_user_id in seen_user_ids:
                raise invalid_request_error("recipients must not contain duplicate recipientUserUuid values")
            seen_user_ids.add(recipient_user_id)
            normalized.append(
                {
                    "recipient_user_id": recipient_user_id,
                    "recipient_email": self._normalize_required_text(recipient.recipientEmail, field_name="recipientEmail"),
                    "recipient_name": self._normalize_required_text(recipient.recipientName, field_name="recipientName"),
                }
            )
        return normalized

    def _find_existing_by_dedupe_key(self, payload: SystemNotificationCreateRequest) -> Notification | None:
        if not payload.dedupeKey:
            return None
        for recipient in payload.recipients:
            rows, _, _, _ = self.recipients.list_by_user(
                recipient_user_id=recipient.recipientUserId,
                include_hidden=True,
                notification_type=payload.notificationType,
                page=1,
                page_size=100,
            )
            for row in rows:
                metadata = row.notification.metadata_json or {}
                if metadata.get("dedupeKey") == payload.dedupeKey:
                    return row.notification
        return None

    def _normalize_required_text(self, value: str | None, *, field_name: str) -> str:
        normalized = self._normalize_optional_text(value)
        if not normalized:
            raise invalid_request_error(f"{field_name} is required")
        return normalized

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _is_update_payload_empty(self, payload: NotificationUpdateRequest) -> bool:
        return (
            payload.notificationType is None
            and payload.title is None
            and payload.body is None
            and payload.targetType is None
            and payload.targetId is None
            and payload.metadataJson is None
        )

    def _to_notification_read(self, notification: Notification) -> NotificationRead:
        return NotificationRead(
            notificationId=notification.notification_id,
            notificationUuid=encode_notification_uuid(notification.notification_id),
            actorUserId=notification.actor_user_id,
            actorUserUuid=encode_user_uuid(notification.actor_user_id) if notification.actor_user_id is not None else None,
            actorEmail=notification.actor_email,
            actorName=notification.actor_name,
            notificationType=notification.notification_type,
            title=notification.title,
            body=notification.body,
            targetType=notification.target_type,
            targetId=notification.target_id,
            metadataJson=notification.metadata_json,
            createdAt=notification.created_at,
            updatedAt=notification.updated_at,
        )

    def _to_recipient_read(self, recipient: NotificationRecipient) -> NotificationRecipientRead:
        notification = recipient.notification
        return NotificationRecipientRead(
            notificationId=notification.notification_id,
            notificationUuid=encode_notification_uuid(notification.notification_id),
            actorUserId=notification.actor_user_id,
            actorUserUuid=encode_user_uuid(notification.actor_user_id) if notification.actor_user_id is not None else None,
            actorEmail=notification.actor_email,
            actorName=notification.actor_name,
            notificationType=notification.notification_type,
            title=notification.title,
            body=notification.body,
            targetType=notification.target_type,
            targetId=notification.target_id,
            metadataJson=notification.metadata_json,
            createdAt=notification.created_at,
            updatedAt=notification.updated_at,
            recipientUserId=recipient.recipient_user_id,
            recipientUserUuid=encode_user_uuid(recipient.recipient_user_id),
            recipientEmail=recipient.recipient_email,
            recipientName=recipient.recipient_name,
            isRead=recipient.is_read,
            readAt=recipient.read_at,
            isHidden=recipient.is_hidden,
            hiddenAt=recipient.hidden_at,
            receivedAt=recipient.created_at,
        )

    def _to_state_response(self, recipient: NotificationRecipient) -> NotificationRecipientStateResponse:
        return NotificationRecipientStateResponse(
            notificationId=recipient.notification_id,
            notificationUuid=encode_notification_uuid(recipient.notification_id),
            recipientUserId=recipient.recipient_user_id,
            recipientUserUuid=encode_user_uuid(recipient.recipient_user_id),
            isRead=recipient.is_read,
            readAt=recipient.read_at,
            isHidden=recipient.is_hidden,
            hiddenAt=recipient.hidden_at,
        )
