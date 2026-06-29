from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.schemas.short_answer import ShortAnswerEvaluationRequest
from platform_common.http import post_json


class ShortAnswerAIClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def evaluate_submission(self, payload: ShortAnswerEvaluationRequest) -> dict[str, Any]:
        return post_json(
            url=f"{settings.ai_service_url}/internal/short-answer/evaluate",
            payload=payload.model_dump(mode="json"),
            headers=self._internal_headers(),
            timeout=20,
        )
