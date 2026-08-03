from __future__ import annotations

import json

from app.core.prompts import get_prompt_template
from app.services.providers.model_service import AIModelInvocationService
from app.services.providers.types import ProviderConfigurationError, ProviderInvocationError, ProviderQuotaError
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationCandidateSetRead,
    QuizGenerationContextRead,
    QuizGenerationPlanRead,
    QuizGenerationProfileContextRead,
    QuizGenerationRequest,
    RetrievalContextRead,
)
from app.services.provider_error_messages import QUIZ_GENERATION_UNAVAILABLE
from platform_common.errors import http_error, invalid_request_error


class QuizCandidateGenerationService:
    PROMPT_TEMPLATE_NAME = "quiz_generation_candidates_v1"
    MAX_PROVIDER_ATTEMPTS = 3
    RETRY_BACKOFF_SECONDS = (1, 2)

    def __init__(self, session=None) -> None:
        self.session = session

    def generate_candidates(
        self,
        *,
        request: QuizGenerationRequest,
        context: QuizGenerationContextRead,
        retrieval_context: RetrievalContextRead,
        plan: QuizGenerationPlanRead,
        profile_context: QuizGenerationProfileContextRead | None = None,
    ) -> QuizGenerationCandidateSetRead:
        prompt_template = get_prompt_template(self.PROMPT_TEMPLATE_NAME)
        prompt = self._build_prompt(
            request=request,
            context=context,
            retrieval_context=retrieval_context,
            plan=plan,
            profile_context=profile_context,
        )
        try:
            return AIModelInvocationService(self.session).generate_json(
                prompt=prompt,
                system_instruction=prompt_template.system_instruction,
                model_id=retrieval_context.chatModelId,
                user_id=None,
                temperature=0.2,
                max_output_tokens=4000,
                validator=QuizGenerationCandidateSetRead.model_validate,
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
        plan: QuizGenerationPlanRead,
        profile_context: QuizGenerationProfileContextRead | None,
    ) -> str:
        output_shape = {
            "questionCount": context.questionCountPerAttempt,
            "questions": [
                {
                    "questionText": "Example question?",
                    "explanationText": "Why the correct answer is right.",
                    "sortOrder": 1,
                    "isActive": True,
                    "options": [
                        {"optionLabel": "A", "optionText": "Correct option", "sortOrder": 1, "isCorrect": True},
                        {"optionLabel": "B", "optionText": "Distractor", "sortOrder": 2, "isCorrect": False},
                    ],
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
            "Approved quiz plan JSON:\n"
            f"{json.dumps(plan.model_dump(mode='json'), ensure_ascii=True, indent=2)}\n\n"
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
