import json
from urllib import error, request

from fastapi import HTTPException

from app.core.config import settings
from platform_common.errors import forum_post_pin_forbidden_error, invalid_request_error


class CourseManagementClient:
    def assert_pin_access(self, *, course_uuid: str, token: str) -> None:
        req = request.Request(
            url=f"{settings.learning_service_url}/courses/{course_uuid}/management",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="GET",
        )

        try:
            with request.urlopen(req, timeout=10):
                return
        except error.HTTPError as exc:
            if exc.code == 403:
                raise forum_post_pin_forbidden_error() from exc
            if exc.code == 404:
                raise invalid_request_error("Course not found for this forum post") from exc

            detail: object = "Unable to verify course moderation access"
            try:
                body = exc.read().decode("utf-8")
                parsed = json.loads(body) if body else {}
                detail = parsed.get("detail", detail)
            except Exception:
                pass

            raise HTTPException(status_code=exc.code, detail=detail) from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "LEARNING_SERVICE_UNAVAILABLE", "message": "Learning service unavailable"},
            ) from exc
