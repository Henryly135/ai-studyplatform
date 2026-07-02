from __future__ import annotations

import logging

from fastapi import HTTPException

from app.core.config import settings
from app.services.workflows.quiz_generation.schemas import (
    CreatedQuizQuestionRead,
    QuizGeneratedAttemptStartResponse,
    QuizGenerationCandidateSetRead,
    QuizGenerationContextRead,
)
from platform_common.errors import invalid_request_error
from platform_common.http import post_json


logger = logging.getLogger(__name__)


class LearningQuizGenerationClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def fetch_context(self, *, course_uuid: str, module_uuid: str) -> QuizGenerationContextRead:
        try:
            payload = post_json(
                url=f"{settings.learning_service_url}/internal/quiz-generation/context",
                payload={
                    "courseUuid": course_uuid,
                    "moduleUuid": module_uuid,
                },
                headers=self._internal_headers(),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to fetch quiz generation context from learning service",
                extra={"courseUuid": course_uuid, "moduleUuid": module_uuid},
            )
            raise invalid_request_error("Unable to load quiz generation context") from exc

        return QuizGenerationContextRead.model_validate(payload)

    def ensure_learner_quiz_access(self, *, course_uuid: str, module_uuid: str, learner_id: int) -> None:
        try:
            post_json(
                url=f"{settings.learning_service_url}/internal/quiz-generation/learner-access",
                payload={
                    "courseUuid": course_uuid,
                    "moduleUuid": module_uuid,
                    "learnerId": learner_id,
                },
                headers=self._internal_headers(),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to verify learner quiz access in learning service",
                extra={"courseUuid": course_uuid, "moduleUuid": module_uuid, "learnerId": learner_id},
            )
            raise invalid_request_error("Unable to verify quiz access") from exc

    def ensure_authoring_quiz_access(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        actor_id: int,
        actor_identity: str,
    ) -> None:
        try:
            post_json(
                url=f"{settings.learning_service_url}/internal/quiz-generation/authoring-access",
                payload={
                    "courseUuid": course_uuid,
                    "moduleUuid": module_uuid,
                    "actorId": actor_id,
                    "actorIdentity": actor_identity,
                },
                headers=self._internal_headers(),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to verify quiz authoring access in learning service",
                extra={"courseUuid": course_uuid, "moduleUuid": module_uuid, "actorId": actor_id},
            )
            raise invalid_request_error("Unable to verify quiz authoring access") from exc

    def batch_create_questions(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        candidate_set: QuizGenerationCandidateSetRead,
        purpose: str = "authoring",
    ) -> list[CreatedQuizQuestionRead]:
        try:
            payload = post_json(
                url=f"{settings.learning_service_url}/internal/quiz-generation/questions/batch-create",
                payload={
                    "courseUuid": course_uuid,
                    "moduleUuid": module_uuid,
                    "purpose": purpose,
                    "questions": candidate_set.model_dump(mode="json")["questions"],
                },
                headers=self._internal_headers(),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to persist generated quiz questions in learning service",
                extra={"courseUuid": course_uuid, "moduleUuid": module_uuid},
            )
            raise invalid_request_error("Unable to persist generated quiz questions") from exc

        questions = payload.get("createdQuestions")
        if not isinstance(questions, list):
            raise invalid_request_error("Learning service returned an invalid question creation response")
        return [CreatedQuizQuestionRead.model_validate(item) for item in questions]

    def start_generated_attempt_internal(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        learner_id: int,
        question_uuids: list[str],
    ) -> QuizGeneratedAttemptStartResponse:
        try:
            payload = post_json(
                url=f"{settings.learning_service_url}/internal/quiz-generation/generated-attempt-sessions",
                payload={
                    "courseUuid": course_uuid,
                    "moduleUuid": module_uuid,
                    "learnerId": learner_id,
                    "questionUuids": question_uuids,
                },
                headers=self._internal_headers(),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to start generated quiz attempt in learning service",
                extra={"courseUuid": course_uuid, "moduleUuid": module_uuid},
            )
            raise invalid_request_error("Unable to start generated quiz attempt") from exc

        return QuizGeneratedAttemptStartResponse.model_validate(payload)
