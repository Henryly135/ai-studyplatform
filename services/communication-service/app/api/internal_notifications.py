from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_internal_request
from app.db.session import get_db_session
from app.schemas.notification import NotificationRead, SystemNotificationCreateRequest
from app.services.notification_service import NotificationService


router = APIRouter(prefix="/internal/notifications", tags=["internal-notifications"])


@router.post("/system", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
def create_system_notification(
    payload: SystemNotificationCreateRequest,
    _: None = Depends(require_internal_request),
    session: Session = Depends(get_db_session),
) -> NotificationRead:
    return NotificationService(session).create_system_notification(payload=payload)
