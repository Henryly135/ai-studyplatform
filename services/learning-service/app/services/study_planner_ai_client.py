from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.schemas.study_planner import StudyPlanCreateRequest
from platform_common.http import post_json


class StudyPlannerAIClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def generate_plan(self, payload: StudyPlanCreateRequest) -> dict[str, Any]:
        return post_json(
            url=f"{settings.ai_service_url}/internal/study-planner/generate",
            payload=payload.model_dump(mode="json"),
            headers=self._internal_headers(),
            timeout=20,
        )
