from __future__ import annotations

import json

from app.core.prompts import get_prompt_template
from app.services.providers.model_service import AIModelInvocationService
from app.services.providers.types import ProviderConfigurationError, ProviderInvocationError, ProviderQuotaError
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationContextRead,
    QuizGenerationPlanRead,
    QuizGenerationProfileContextRead,
    QuizGenerationRequest,
    RetrievalContextRead,
)
from app.services.provider_error_messages import QUIZ_GENERATION_UNAVAILABLE
from platform_common.errors import http_error, invalid_request_error


class QuizGenerationPlanningService:
    PROMPT_TEMPLATE_NAME = "quiz_generation_plan_v1"
    MAX_PROVIDER_ATTEMPTS = 3
    RETRY_BACKOFF_SECONDS = (1, 2)

    def build_plan(
        self,
        *,
        request: QuizGenerationRequest,
        context: QuizGenerationContextRead,
        retrieval_context: RetrievalContextRead,
        profile_context: QuizGenerationProfileContextRead | None = None,
    ) -> QuizGenerationPlanRead:
        prompt_template = get_prompt_template(self.PROMPT_TEMPLATE_NAME)
        prompt = self._build_prompt(
            request=request,
            context=context,
            retrieval_context=retrieval_context,
            profile_context=profile_context,
        )
        try:
            return AIModelInvocationService().generate_json(
                prompt=prompt,
                system_instruction=prompt_template.system_instruction,
                temperature=0.2,
                max_output_tokens=1800,
                validator=QuizGenerationPlanRead.model_validate,
            )
        except ProviderQuotaError as exc:
            raise http_error(status_code=429, code="AI_QUOTA_EXCEEDED", message=QUIZ_GENERATION_UNAVAILABLE) from exc
        except ProviderConfigurationError as exc:
            raise invalid_request_error(QUIZ_GENERATION_UNAVAILABLE) from exc
        except ProviderInvocationError as exc:
            raise http_error(status_code=503, code="AI_PROVIDER_UNAVAILABLE", message=QUIZ_GENERATION_UNAVAILABLE) from exc

    def _build_prompt(
        self,
        *,
        request: QuizGenerationRequest,
        context: QuizGenerationContextRead,
        retrieval_context: RetrievalContextRead,
        profile_context: QuizGenerationProfileContextRead | None,
    ) -> str:
        output_shape = {
            "titleSuggestion": context.quizTitle,
            "overview": "Short overview of coverage and difficulty mix.",
            "plannedQuestionCount": context.questionCountPerAttempt,
            "questions": [
                {
                    "sortOrder": 1,
                    "learningObjective": "Assess a concrete module concept",
                    "difficulty": "medium",
                    "questionStyle": "multiple_choice",
                    "rationale": "Why this question should exist",
                }
            ],
        }
        return (
            "Quiz generation request JSON:\n"
            f"{json.dumps(request.model_dump(mode='json'), ensure_ascii=True, indent=2)}\n\n"
            "Existing quiz configuration JSON:\n"
            f"{json.dumps(context.model_dump(mode='json'), ensure_ascii=True, indent=2)}\n\n"
            "Retrieved learning context JSON:\n"
            f"{json.dumps(retrieval_context.model_dump(mode='json'), ensure_ascii=True, indent=2)}\n\n"
            "Learner profile context JSON:\n"
            f"{json.dumps(self._profile_context_payload(profile_context), ensure_ascii=True, indent=2)}\n\n"
            "Required output JSON shape:\n"
            f"{json.dumps(output_shape, ensure_ascii=True, indent=2)}\n"
        )

    def _profile_context_payload(self, profile_context: QuizGenerationProfileContextRead | None) -> dict:
        if profile_context is None:
            return {"available": False, "reason": "learner_profile_context_not_requested"}
        return {
            "available": True,
            "learnerId": profile_context.learnerId,
            "globalProfile": profile_context.globalProfile.model_dump(mode="json"),
            "moduleProfile": profile_context.moduleProfile.model_dump(mode="json"),
        }
