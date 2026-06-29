from __future__ import annotations

from app.core.config import settings
from platform_common.http import post_json


class ModuleProfileInitializationClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def initialize_modules(
        self,
        *,
        learner_id: int,
        course_uuid: str,
        module_uuids: list[str],
        trigger_source: str,
    ) -> dict[str, object]:
        return post_json(
            url=f"{settings.ai_service_url}/internal/profiles/module/init-batch",
            payload={
                "learnerId": learner_id,
                "courseUuid": course_uuid,
                "moduleUuids": module_uuids,
                "triggerSource": trigger_source,
            },
            headers=self._internal_headers(),
            timeout=5,
        )
