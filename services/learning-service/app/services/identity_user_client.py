from __future__ import annotations

from app.core.config import settings
from platform_common.http import post_json


class IdentityUserClient:
    def lookup_users_by_ids(self, *, user_ids: list[int]) -> dict[int, dict[str, object]]:
        if not user_ids:
            return {}

        response = post_json(
            url=f"{settings.identity_service_url}/internal/users/lookup",
            payload={"userIds": user_ids},
            headers={"X-Internal-Token": settings.internal_api_token},
        )

        users = response.get("users", [])
        if not isinstance(users, list):
            return {}

        profiles_by_user_id: dict[int, dict[str, object]] = {}
        for user in users:
            if not isinstance(user, dict):
                continue

            user_id = user.get("id")
            if not isinstance(user_id, int):
                continue

            profiles_by_user_id[user_id] = user

        return profiles_by_user_id
