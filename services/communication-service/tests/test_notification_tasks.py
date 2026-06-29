from types import SimpleNamespace

from app.tasks.notifications import dispatch_educator_approval_request_created_task


def test_dispatch_educator_approval_request_created_task_persists_notification(monkeypatch):
    # Tests that the educator approval notification task persists notification and recipient rows.
    committed = {"value": False}
    notification_payload = {}
    recipient_payload = {}

    class FakeSession:
        def commit(self):
            committed["value"] = True

        def close(self):
            pass

    class FakeNotificationRepository:
        def __init__(self, session):
            self.session = session

        def create(self, **kwargs):
            notification_payload.update(kwargs)
            return SimpleNamespace(notification_id=101)

    class FakeRecipientRepository:
        def __init__(self, session):
            self.session = session

        def create_many(self, *, notification_id, recipients):
            recipient_payload["notification_id"] = notification_id
            recipient_payload["recipients"] = recipients
            return []

    monkeypatch.setattr("app.tasks.notifications.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr("app.tasks.notifications.NotificationRepository", FakeNotificationRepository)
    monkeypatch.setattr("app.tasks.notifications.NotificationRecipientRepository", FakeRecipientRepository)

    result = dispatch_educator_approval_request_created_task.run(
        {
            "actorUserId": 7,
            "actorEmail": "teacher@example.com",
            "actorName": "Teacher T",
            "requestUuid": "request-uuid",
            "title": "New educator approval request",
            "body": "Teacher T submitted an educator registration request.",
            "metadataJson": {"requestUuid": "request-uuid"},
            "recipients": [
                {
                    "recipient_user_id": 10,
                    "recipient_email": "admin@example.com",
                    "recipient_name": "Admin One",
                }
            ],
        }
    )

    assert committed["value"] is True
    assert notification_payload["notification_type"] == "educator_approval_request_created"
    assert recipient_payload["notification_id"] == 101
    assert len(recipient_payload["recipients"]) == 1
    assert result == {"notificationId": 101, "recipientCount": 1}
