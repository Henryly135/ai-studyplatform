from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification

_UNSET = object()


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, notification_id: int) -> Notification | None:
        return self.session.get(Notification, notification_id)

    def list_paginated(
        self,
        *,
        notification_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int, int, int]:
        stmt = select(Notification).order_by(Notification.created_at.desc(), Notification.notification_id.desc())
        if notification_type:
            stmt = stmt.where(Notification.notification_type == notification_type)
        return self._paginate(stmt, page=page, page_size=page_size)

    def create(
        self,
        *,
        notification_type: str,
        title: str,
        body: str,
        actor_user_id: int | None = None,
        actor_email: str | None = None,
        actor_name: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata_json: dict | None = None,
    ) -> Notification:
        notification = Notification(
            notification_type=notification_type,
            title=title,
            body=body,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            actor_name=actor_name,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata_json,
        )
        self.session.add(notification)
        self.session.flush()
        return notification

    def update(
        self,
        notification: Notification,
        *,
        notification_type: str | object = _UNSET,
        title: str | object = _UNSET,
        body: str | object = _UNSET,
        actor_user_id: int | None | object = _UNSET,
        actor_email: str | None | object = _UNSET,
        actor_name: str | None | object = _UNSET,
        target_type: str | None | object = _UNSET,
        target_id: str | None | object = _UNSET,
        metadata_json: dict | None | object = _UNSET,
    ) -> Notification:
        if notification_type is not _UNSET:
            notification.notification_type = notification_type
        if title is not _UNSET:
            notification.title = title
        if body is not _UNSET:
            notification.body = body
        if actor_user_id is not _UNSET:
            notification.actor_user_id = actor_user_id
        if actor_email is not _UNSET:
            notification.actor_email = actor_email
        if actor_name is not _UNSET:
            notification.actor_name = actor_name
        if target_type is not _UNSET:
            notification.target_type = target_type
        if target_id is not _UNSET:
            notification.target_id = target_id
        if metadata_json is not _UNSET:
            notification.metadata_json = metadata_json
        self.session.flush()
        return notification

    def delete(self, notification: Notification) -> None:
        self.session.delete(notification)
        self.session.flush()

    def _paginate(
        self,
        stmt: Select[tuple[Notification]],
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[Notification], int, int, int]:
        safe_page = max(1, page)
        safe_page_size = max(1, page_size)
        total = self.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
        bounded_page = min(safe_page, total_pages)
        offset = (bounded_page - 1) * safe_page_size
        items = list(self.session.scalars(stmt.offset(offset).limit(safe_page_size)))
        return items, total, bounded_page, total_pages
