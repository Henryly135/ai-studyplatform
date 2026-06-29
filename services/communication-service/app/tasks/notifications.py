from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.repositories.notification_recipient_repository import NotificationRecipientRepository
from app.repositories.notification_repository import NotificationRepository


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    name="app.tasks.notifications.dispatch_educator_approval_request_created_task",
)
def dispatch_educator_approval_request_created_task(self, payload: dict) -> dict[str, int]:
    session = SessionLocal()
    try:
        notification = NotificationRepository(session).create(
            notification_type="educator_approval_request_created",
            title=str(payload["title"]).strip(),
            body=str(payload["body"]).strip(),
            actor_user_id=int(payload["actorUserId"]),
            actor_email=(str(payload.get("actorEmail") or "").strip() or None),
            actor_name=(str(payload.get("actorName") or "").strip() or None),
            target_type="educator_approval_request",
            target_id=str(payload["requestUuid"]).strip(),
            metadata_json=payload.get("metadataJson"),
        )
        NotificationRecipientRepository(session).create_many(
            notification_id=notification.notification_id,
            recipients=list(payload["recipients"]),
        )
        session.commit()
        return {
            "notificationId": int(notification.notification_id),
            "recipientCount": len(payload["recipients"]),
        }
    finally:
        session.close()
