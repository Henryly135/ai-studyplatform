from __future__ import annotations

from app.core.config import settings
from platform_common.http import post_json


class CommunicationNotificationClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def send_learning_profile_initialization_prompt(self, *, learner_id: int) -> dict[str, object]:
        frontend_path = "/home/ai/profile-init"
        return post_json(
            url=f"{settings.communication_service_url}/internal/notifications/system",
            payload={
                "notificationType": "learning_profile_initialization_prompt",
                "title": "Complete your Learning Profile",
                "body": (
                    "Complete your Learning Profile so the AI can support you more "
                    "consistently across generated quizzes and future learning activities."
                ),
                "targetType": "learning_profile_init",
                "targetId": "learning-profile-init",
                "dedupeKey": f"learning_profile_init:learner:{learner_id}",
                "metadataJson": {
                    "action": "initialize_learning_profile",
                    "actionLabel": "Complete Learning Profile",
                    "frontendPath": frontend_path,
                    "source": "quiz_generation",
                },
                "recipients": [
                    {
                        "recipientUserId": learner_id,
                        "recipientName": f"Learner {learner_id}",
                    }
                ],
            },
            headers=self._internal_headers(),
            timeout=5,
        )
