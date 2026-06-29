from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient


class NotificationRecipientRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_many(
        self,
        *,
        notification_id: int,
        recipients: list[dict[str, object]],
    ) -> list[NotificationRecipient]:
        rows: list[NotificationRecipient] = []
        for recipient in recipients:
            row = NotificationRecipient(
                notification_id=notification_id,
                recipient_user_id=int(recipient["recipient_user_id"]),
                recipient_email=str(recipient["recipient_email"]),
                recipient_name=str(recipient["recipient_name"]),
            )
            self.session.add(row)
            rows.append(row)
        self.session.flush()
        return rows

    def get_by_notification_and_user(
        self,
        *,
        notification_id: int,
        recipient_user_id: int,
    ) -> NotificationRecipient | None:
        stmt = (
            select(NotificationRecipient)
            .options(joinedload(NotificationRecipient.notification))
            .where(
                NotificationRecipient.notification_id == notification_id,
                NotificationRecipient.recipient_user_id == recipient_user_id,
            )
        )
        return self.session.scalar(stmt)

    def list_by_user(
        self,
        *,
        recipient_user_id: int,
        include_hidden: bool = False,
        unread_only: bool = False,
        notification_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NotificationRecipient], int, int, int]:
        stmt = (
            select(NotificationRecipient)
            .join(Notification, Notification.notification_id == NotificationRecipient.notification_id)
            .options(joinedload(NotificationRecipient.notification))
            .where(NotificationRecipient.recipient_user_id == recipient_user_id)
            .order_by(Notification.created_at.desc(), Notification.notification_id.desc())
        )
        if not include_hidden:
            stmt = stmt.where(NotificationRecipient.is_hidden.is_(False))
        if unread_only:
            stmt = stmt.where(NotificationRecipient.is_read.is_(False))
        if notification_type:
            stmt = stmt.where(Notification.notification_type == notification_type)
        return self._paginate(stmt, page=page, page_size=page_size)

    def count_unread_by_user(self, *, recipient_user_id: int) -> int:
        stmt = select(func.count()).select_from(NotificationRecipient).where(
            NotificationRecipient.recipient_user_id == recipient_user_id,
            NotificationRecipient.is_hidden.is_(False),
            NotificationRecipient.is_read.is_(False),
        )
        return int(self.session.scalar(stmt) or 0)

    def mark_read(
        self,
        recipient: NotificationRecipient,
        *,
        read_at: datetime,
    ) -> NotificationRecipient:
        recipient.is_read = True
        recipient.read_at = read_at
        self.session.flush()
        return recipient

    def mark_unread(self, recipient: NotificationRecipient) -> NotificationRecipient:
        recipient.is_read = False
        recipient.read_at = None
        self.session.flush()
        return recipient

    def mark_all_read(
        self,
        *,
        recipient_user_id: int,
        read_at: datetime,
    ) -> int:
        stmt = (
            select(NotificationRecipient)
            .where(
                NotificationRecipient.recipient_user_id == recipient_user_id,
                NotificationRecipient.is_hidden.is_(False),
                NotificationRecipient.is_read.is_(False),
            )
        )
        rows = list(self.session.scalars(stmt))
        for row in rows:
            row.is_read = True
            row.read_at = read_at
        self.session.flush()
        return len(rows)

    def hide(self, recipient: NotificationRecipient, *, hidden_at: datetime) -> NotificationRecipient:
        recipient.is_hidden = True
        recipient.hidden_at = hidden_at
        self.session.flush()
        return recipient

    def unhide(self, recipient: NotificationRecipient) -> NotificationRecipient:
        recipient.is_hidden = False
        recipient.hidden_at = None
        self.session.flush()
        return recipient

    def _paginate(
        self,
        stmt: Select[tuple[NotificationRecipient]],
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[NotificationRecipient], int, int, int]:
        safe_page = max(1, page)
        safe_page_size = max(1, page_size)
        total = self.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
        bounded_page = min(safe_page, total_pages)
        offset = (bounded_page - 1) * safe_page_size
        items = list(self.session.scalars(stmt.offset(offset).limit(safe_page_size)))
        return items, total, bounded_page, total_pages
