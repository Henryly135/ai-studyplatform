from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.schemas.notification import SystemNotificationCreateRequest
from app.services.notification_service import NotificationService


NOW = datetime(2026, 1, 1, 0, 0, 0)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item) -> None:
        _ = item


def test_create_system_notification_persists_system_actor_and_dedupe_key():
    # Tests that system notifications persist a system actor and dedupe key metadata.
    session = FakeSession()
    created_notification = {}
    created_recipients = {}

    class FakeNotificationRepository:
        def __init__(self, session):
            self.session = session

        def create(self, **kwargs):
            created_notification.update(kwargs)
            return SimpleNamespace(
                notification_id=101,
                actor_user_id=kwargs.get("actor_user_id"),
                actor_email=kwargs.get("actor_email"),
                actor_name=kwargs.get("actor_name"),
                notification_type=kwargs["notification_type"],
                title=kwargs["title"],
                body=kwargs["body"],
                target_type=kwargs.get("target_type"),
                target_id=kwargs.get("target_id"),
                metadata_json=kwargs.get("metadata_json"),
                created_at=NOW,
                updated_at=NOW,
            )

    class FakeRecipientRepository:
        def __init__(self, session):
            self.session = session

        def list_by_user(self, **kwargs):
            return [], 0, 1, 1

        def create_many(self, *, notification_id, recipients):
            created_recipients["notification_id"] = notification_id
            created_recipients["recipients"] = recipients
            return []

    service = NotificationService(session)
    service.notifications = FakeNotificationRepository(session)
    service.recipients = FakeRecipientRepository(session)

    result = service.create_system_notification(
        payload=SystemNotificationCreateRequest.model_validate(
            {
                "notificationType": "learning_profile_initialization_prompt",
                "title": "Complete your Learning Profile",
                "body": "Please initialize your learning profile.",
                "targetType": "learning_profile_init",
                "targetId": "learning-profile-init",
                "dedupeKey": "learning_profile_init:learner:77",
                "metadataJson": {"frontendPath": "/home/ai/profile-init"},
                "recipients": [{"recipientUserId": 77}],
            }
        )
    )

    assert session.committed is True
    assert result.notificationType == "learning_profile_initialization_prompt"
    assert created_notification["actor_name"] == "System"
    assert created_notification["metadata_json"]["dedupeKey"] == "learning_profile_init:learner:77"
    assert created_recipients["recipients"][0]["recipient_user_id"] == 77


def test_create_system_notification_returns_existing_when_dedupe_key_matches():
    # Tests that matching dedupe keys return the existing notification without committing.
    session = FakeSession()
    existing_notification = SimpleNamespace(
        notification_id=202,
        actor_user_id=None,
        actor_email=None,
        actor_name="System",
        notification_type="learning_profile_initialization_prompt",
        title="Existing prompt",
        body="Already sent.",
        target_type="learning_profile_init",
        target_id="learning-profile-init",
        metadata_json={"dedupeKey": "learning_profile_init:learner:77"},
        created_at=NOW,
        updated_at=NOW,
    )

    class FakeNotificationRepository:
        def __init__(self, session):
            self.session = session

        def create(self, **kwargs):
            raise AssertionError("create should not be called when dedupe matches")

    class FakeRecipientRepository:
        def __init__(self, session):
            self.session = session

        def list_by_user(self, **kwargs):
            return [SimpleNamespace(notification=existing_notification)], 1, 1, 1

    service = NotificationService(session)
    service.notifications = FakeNotificationRepository(session)
    service.recipients = FakeRecipientRepository(session)

    result = service.create_system_notification(
        payload=SystemNotificationCreateRequest.model_validate(
            {
                "notificationType": "learning_profile_initialization_prompt",
                "title": "Complete your Learning Profile",
                "body": "Please initialize your learning profile.",
                "dedupeKey": "learning_profile_init:learner:77",
                "recipients": [{"recipientUserId": 77}],
            }
        )
    )

    assert session.committed is False
    assert result.notificationId == 202
