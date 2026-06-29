from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.schemas.quiz import EducatorQuizDraftGenerateRequest
from platform_common.http import post_json


class EducatorQuizDraftAIClient:
    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Token": settings.internal_api_token}

    def generate_draft(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        educator_id: int,
        course_title: str,
        module_title: str,
        quiz_title: str,
        available_question_count: int,
        payload: EducatorQuizDraftGenerateRequest,
    ) -> dict[str, Any]:
        return post_json(
            url=f"{settings.ai_service_url}/internal/quiz-generation/educator-draft",
            payload={
                "courseUuid": course_uuid,
                "moduleUuid": module_uuid,
                "educatorId": educator_id,
                "courseTitle": course_title,
                "moduleTitle": module_title,
                "quizTitle": quiz_title,
                "questionCount": payload.questionCount,
                "availableQuestionCount": available_question_count,
                "timeLimitSeconds": payload.timeLimitSeconds,
                "shuffleQuestions": payload.shuffleQuestions,
                "shuffleOptions": payload.shuffleOptions,
                "difficulty": payload.difficulty,
                "questionTypes": payload.questionTypes,
                "learningObjectives": payload.learningObjectives,
                "materialScope": payload.materialScope,
                "additionalInstructions": payload.additionalInstructions,
            },
            headers=self._internal_headers(),
            timeout=30,
        )
