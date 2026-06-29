from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_identity_permission
from app.core.time import now_local
from app.core.uuid_codec import decode_notification_uuid
from app.db.session import get_db_session
from app.schemas.notification import (
    MarkAllNotificationsReadResponse,
    NotificationCreateRequest,
    PaginatedNotificationResponse,
    NotificationRead,
    NotificationRecipientRead,
    NotificationRecipientStateResponse,
    NotificationUnreadCountResponse,
    NotificationUpdateRequest,
    PaginatedNotificationRecipientResponse,
)
from app.services.notification_service import NotificationService
from platform_common.permissions.codes import NOTIFICATION_MANAGE, NOTIFICATION_READ


router = APIRouter(tags=["notifications"])
@router.get("/notifications", response_model=PaginatedNotificationResponse)
def list_notifications(
    notification_type: str | None = Query(default=None, alias="notificationType"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_MANAGE)),
    session: Session = Depends(get_db_session),
) -> PaginatedNotificationResponse:
    _ = current_user
    return NotificationService(session).list_all_notifications(
        notification_type=notification_type,
        page=page,
        page_size=page_size,
    )


@router.post("/notifications", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationCreateRequest,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_MANAGE)),
    session: Session = Depends(get_db_session),
) -> NotificationRead:
    return NotificationService(session).create_notification(payload=payload, current_user=current_user)


@router.get("/notifications/{notification_uuid}", response_model=NotificationRead)
def get_notification(
    notification_uuid: str,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_MANAGE)),
    session: Session = Depends(get_db_session),
) -> NotificationRead:
    _ = current_user
    return NotificationService(session).get_notification(notification_id=decode_notification_uuid(notification_uuid))


@router.patch("/notifications/{notification_uuid}", response_model=NotificationRead)
def update_notification(
    notification_uuid: str,
    payload: NotificationUpdateRequest,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_MANAGE)),
    session: Session = Depends(get_db_session),
) -> NotificationRead:
    _ = current_user
    return NotificationService(session).update_notification(
        notification_id=decode_notification_uuid(notification_uuid),
        payload=payload,
    )


@router.delete("/notifications/{notification_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_uuid: str,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_MANAGE)),
    session: Session = Depends(get_db_session),
) -> Response:
    _ = current_user
    NotificationService(session).delete_notification(notification_id=decode_notification_uuid(notification_uuid))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/notifications", response_model=PaginatedNotificationRecipientResponse)
def list_notifications_for_current_user(
    include_hidden: bool = Query(default=False, alias="includeHidden"),
    unread_only: bool = Query(default=False, alias="unreadOnly"),
    notification_type: str | None = Query(default=None, alias="notificationType"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_READ)),
    session: Session = Depends(get_db_session),
) -> PaginatedNotificationRecipientResponse:
    recipient_user_id = int(current_user["id"])
    return NotificationService(session).list_notifications(
        recipient_user_id=recipient_user_id,
        include_hidden=include_hidden,
        unread_only=unread_only,
        notification_type=notification_type,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/me/notifications/unread-count",
    response_model=NotificationUnreadCountResponse,
)
def get_unread_count(
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_READ)),
    session: Session = Depends(get_db_session),
) -> NotificationUnreadCountResponse:
    recipient_user_id = int(current_user["id"])
    return NotificationService(session).count_unread_notifications(recipient_user_id=recipient_user_id)


@router.post(
    "/me/notifications/read-all",
    response_model=MarkAllNotificationsReadResponse,
)
def mark_all_notifications_read(
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_READ)),
    session: Session = Depends(get_db_session),
) -> MarkAllNotificationsReadResponse:
    recipient_user_id = int(current_user["id"])
    return NotificationService(session).mark_all_notifications_read(
        recipient_user_id=recipient_user_id,
        read_at=now_local(),
    )


@router.get(
    "/me/notifications/{notification_uuid}",
    response_model=NotificationRecipientRead,
)
def get_notification_for_current_user(
    notification_uuid: str,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_READ)),
    session: Session = Depends(get_db_session),
) -> NotificationRecipientRead:
    recipient_user_id = int(current_user["id"])
    return NotificationService(session).get_recipient_notification(
        notification_id=decode_notification_uuid(notification_uuid),
        recipient_user_id=recipient_user_id,
    )


@router.patch(
    "/me/notifications/{notification_uuid}/read",
    response_model=NotificationRecipientStateResponse,
)
def mark_notification_read(
    notification_uuid: str,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_READ)),
    session: Session = Depends(get_db_session),
) -> NotificationRecipientStateResponse:
    recipient_user_id = int(current_user["id"])
    return NotificationService(session).mark_notification_read(
        notification_id=decode_notification_uuid(notification_uuid),
        recipient_user_id=recipient_user_id,
        read_at=now_local(),
    )


@router.patch(
    "/me/notifications/{notification_uuid}/unread",
    response_model=NotificationRecipientStateResponse,
)
def mark_notification_unread(
    notification_uuid: str,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_READ)),
    session: Session = Depends(get_db_session),
) -> NotificationRecipientStateResponse:
    recipient_user_id = int(current_user["id"])
    return NotificationService(session).mark_notification_unread(
        notification_id=decode_notification_uuid(notification_uuid),
        recipient_user_id=recipient_user_id,
    )


@router.delete(
    "/me/notifications/{notification_uuid}",
    response_model=NotificationRecipientStateResponse,
)
def hide_notification(
    notification_uuid: str,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_READ)),
    session: Session = Depends(get_db_session),
) -> NotificationRecipientStateResponse:
    recipient_user_id = int(current_user["id"])
    return NotificationService(session).hide_notification(
        notification_id=decode_notification_uuid(notification_uuid),
        recipient_user_id=recipient_user_id,
        hidden_at=now_local(),
    )


@router.patch(
    "/me/notifications/{notification_uuid}/restore",
    response_model=NotificationRecipientStateResponse,
)
def restore_notification(
    notification_uuid: str,
    current_user: dict = Depends(require_identity_permission(NOTIFICATION_READ)),
    session: Session = Depends(get_db_session),
) -> NotificationRecipientStateResponse:
    recipient_user_id = int(current_user["id"])
    return NotificationService(session).unhide_notification(
        notification_id=decode_notification_uuid(notification_uuid),
        recipient_user_id=recipient_user_id,
    )
