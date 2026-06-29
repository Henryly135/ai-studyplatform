from __future__ import annotations

import logging

from fastapi import HTTPException

from app.core.config import settings
from app.services.workflows.profile_update.schemas import QuizSignalSummaryRead
from platform_common.http import post_json


logger = logging.getLogger(__name__)


class LearningQuizSignalClient:
    def fetch_summary(
        self,
        *,
        course_id: int,
        module_id: int,
        learner_id: int,
        max_attempts: int = 2,
    ) -> QuizSignalSummaryRead:
        try:
            payload = post_json(
                url=f"{settings.learning_service_url}/internal/profile-update/quiz-signal-summary",
                payload={
                    "courseId": course_id,
                    "moduleId": module_id,
                    "learnerId": learner_id,
                    "maxAttempts": max_attempts,
                },
                headers={"X-Internal-Token": settings.internal_api_token},
            )
            return QuizSignalSummaryRead.model_validate(payload)
        except HTTPException as exc:
            logger.warning(
                "Failed to fetch quiz signal summary from learning service",
                extra={
                    "courseId": course_id,
                    "moduleId": module_id,
                    "learnerId": learner_id,
                    "statusCode": exc.status_code,
                },
            )
        except Exception:
            logger.exception(
                "Unexpected error while decoding quiz signal summary from learning service",
                extra={
                    "courseId": course_id,
                    "moduleId": module_id,
                    "learnerId": learner_id,
                },
            )

        return QuizSignalSummaryRead(
            available=False,
            unavailableReason="learning_service_unavailable",
            signalStrength="none",
            evidenceCount=0,
            timeWindow=None,
            summary=None,
        )
