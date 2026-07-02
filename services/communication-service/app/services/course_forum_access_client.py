from __future__ import annotations

import logging

from fastapi import HTTPException

from app.core.config import settings
from platform_common.errors import invalid_request_error
from platform_common.http import post_json


logger = logging.getLogger(__name__)


class CourseForumAccessClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def assert_forum_access(self, *, course_uuid: str, current_user: dict) -> None:
        raw_user_id = current_user.get("id")
        identity = current_user.get("identity")
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            raise invalid_request_error("Unable to resolve current user for course forum access") from None
        if not isinstance(identity, str):
            raise invalid_request_error("Unable to resolve current user for course forum access")

        try:
            post_json(
                url=f"{settings.learning_service_url}/internal/course-access/forum",
                payload={
                    "courseUuid": course_uuid,
                    "userId": user_id,
                    "identity": identity,
                },
                headers=self._internal_headers(),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to verify course forum access in learning service",
                extra={"courseUuid": course_uuid, "userId": user_id},
            )
            raise invalid_request_error("Unable to verify course forum access") from exc
