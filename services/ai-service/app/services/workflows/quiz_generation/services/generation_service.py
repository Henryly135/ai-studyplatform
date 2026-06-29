from __future__ import annotations

import json
import logging
import time

from app.core.config import settings
from app.core.prompts import get_prompt_template
from app.services.providers import AIProviderConfigurationError, AIProviderError, ChatGenerationRequest, get_chat_provider
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationCandidateSetRead,
    QuizGenerationContextRead,
    QuizGenerationPlanRead,
    QuizGenerationProfileContextRead,
    QuizGenerationRequest,
    RetrievalContextRead,
)
from platform_common.errors import http_error, invalid_request_error


logger = logging.getLogger(__name__)


class QuizCandidateGenerationService:
    PROMPT_TEMPLATE_NAME = "quiz_generation_candidates_v1"
    MAX_PROVIDER_ATTEMPTS = 3
    RETRY_BACKOFF_SECONDS = (1, 2)

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
            provider = get_chat_provider()
        except AIProviderConfigurationError as exc:
            raise invalid_request_error(str(exc)) from exc

        response = None
        for attempt in range(1, self.MAX_PROVIDER_ATTEMPTS + 1):
            try:
                response = provider.generate(
                    ChatGenerationRequest(
                        model=settings.ai_chat_model,
                        system_instruction=prompt_template.system_instruction,
                        contents=prompt,
                        temperature=0.2,
                        max_output_tokens=4000,
                        response_mime_type="application/json",
                    )
                )
                break
            except AIProviderError as exc:
                if exc.error_type not in {"provider_timeout", "transient_network_error"}:
                    raise invalid_request_error(f"Quiz generation failed: {exc}") from exc
                if attempt >= self.MAX_PROVIDER_ATTEMPTS:
                    raise http_error(
                        status_code=503,
                        code="AI_PROVIDER_UNAVAILABLE",
                        message=f"Quiz generation is temporarily unavailable: {exc}",
                    ) from exc
                backoff_seconds = self.RETRY_BACKOFF_SECONDS[min(attempt - 1, len(self.RETRY_BACKOFF_SECONDS) - 1)]
                logger.warning(
                    "Quiz generation hit AI provider error; retrying",
                    extra={
                        "attempt": attempt,
                        "maxAttempts": self.MAX_PROVIDER_ATTEMPTS,
                        "backoffSeconds": backoff_seconds,
                    },
                )
                time.sleep(backoff_seconds)

        content = (response.text or "").strip()
        if not content:
            raise invalid_request_error("Quiz generation returned empty content")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise invalid_request_error("Quiz generation returned invalid JSON") from exc
        return QuizGenerationCandidateSetRead.model_validate(parsed)

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
