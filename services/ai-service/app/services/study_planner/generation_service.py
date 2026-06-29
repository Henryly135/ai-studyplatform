from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.services.providers.factory import get_chat_provider
from app.services.providers.types import (
    AIProviderConfigurationError,
    AIProviderError,
    ChatGenerationRequest,
)
from app.services.study_planner.schemas import (
    StudyPlanContent,
    StudyPlanGenerationRequest,
    StudyPlanGenerationResponse,
    StudyPlanPhase,
    StudyPlanRevisionItem,
    StudyPlanTopic,
)


class StudyPlanGenerationService:
    def generate(self, payload: StudyPlanGenerationRequest) -> StudyPlanGenerationResponse:
        try:
            provider = get_chat_provider()
            result = provider.generate(
                ChatGenerationRequest(
                    model=settings.ai_chat_model,
                    system_instruction=self._system_instruction(),
                    contents=self._prompt(payload),
                    temperature=0.3,
                    max_output_tokens=max(settings.ai_chat_max_output_tokens, 1200),
                    response_mime_type="application/json",
                )
            )
            content = self._parse_provider_content(result.text)
            return StudyPlanGenerationResponse(
                planContent=content,
                provider=provider.provider_name,
                model=settings.ai_chat_model,
                usedFallback=False,
                usageMetadata=result.usage_metadata,
            )
        except (AIProviderConfigurationError, AIProviderError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return StudyPlanGenerationResponse(
                planContent=self._fallback_plan(payload),
                provider="fallback",
                model="deterministic-study-planner-v1",
                usedFallback=True,
                fallbackReason=self._fallback_reason(exc),
                usageMetadata=None,
            )

    def _system_instruction(self) -> str:
        return (
            "You create student study plans. Return only valid JSON with keys "
            "overview, weeklyCommitmentMinutes, phases, topics, revisionSchedule, and rationale. "
            "Use concise, concrete language and do not include markdown."
        )

    def _prompt(self, payload: StudyPlanGenerationRequest) -> str:
        return json.dumps(
            {
                "task": "Generate a study plan with staged phases, topic ordering, revision cadence, and rationale.",
                "goal": payload.goal,
                "availableMinutesPerWeek": payload.availableMinutesPerWeek,
                "targetDate": payload.targetDate.isoformat() if payload.targetDate else None,
                "preferences": payload.preferences,
                "materials": [material.model_dump() for material in payload.materials],
                "responseShape": {
                    "overview": "string",
                    "weeklyCommitmentMinutes": "integer",
                    "phases": [{"title": "string", "focus": "string", "durationDays": "integer", "outcomes": ["string"]}],
                    "topics": [{"title": "string", "reason": "string", "materials": ["string"]}],
                    "revisionSchedule": [{"cadence": "string", "activity": "string"}],
                    "rationale": "string",
                },
            },
            ensure_ascii=True,
        )

    def _parse_provider_content(self, text: str | None) -> StudyPlanContent:
        if not text or not text.strip():
            raise ValueError("Provider returned an empty study plan")
        parsed: Any = json.loads(text)
        if isinstance(parsed, dict) and "planContent" in parsed:
            parsed = parsed["planContent"]
        if not isinstance(parsed, dict):
            raise ValueError("Provider returned an unexpected study plan shape")
        return StudyPlanContent.model_validate(parsed)

    def _fallback_plan(self, payload: StudyPlanGenerationRequest) -> StudyPlanContent:
        material_titles = [material.title for material in payload.materials] or ["your selected materials"]
        topic_inputs = material_titles[:6]
        seen_titles: set[str] = set()
        topics = []
        for title in topic_inputs:
            topic_title = self._unique_topic_title(title, seen_titles)
            topics.append(
                StudyPlanTopic(
                    title=topic_title,
                    reason="Start here because this material directly supports the stated goal.",
                    materials=[title],
                )
            )
        if not topics:
            topics = [
                StudyPlanTopic(
                    title="Core concepts",
                    reason="Build the foundation before moving into practice and review.",
                    materials=[],
                )
            ]

        return StudyPlanContent(
            overview=(
                f"Work toward '{payload.goal}' with a steady weekly commitment of "
                f"{payload.availableMinutesPerWeek} minutes."
            ),
            weeklyCommitmentMinutes=payload.availableMinutesPerWeek,
            phases=[
                StudyPlanPhase(
                    title="Orient and map",
                    focus="Clarify success criteria, skim materials, and identify the highest-value topics.",
                    durationDays=3,
                    outcomes=["Goal checklist", "Prioritized topic list"],
                ),
                StudyPlanPhase(
                    title="Learn and practice",
                    focus="Study the prioritized topics in order, alternating notes with applied practice.",
                    durationDays=10,
                    outcomes=["Completed topic notes", "Practice attempts for each topic"],
                ),
                StudyPlanPhase(
                    title="Review and consolidate",
                    focus="Use spaced review, retrieval practice, and a final gap check.",
                    durationDays=4,
                    outcomes=["Revision log", "Final confidence check"],
                ),
            ],
            topics=topics,
            revisionSchedule=[
                StudyPlanRevisionItem(cadence="After each study block", activity="Write a three-point recall summary."),
                StudyPlanRevisionItem(cadence="Twice per week", activity="Revisit weak topics and redo one practice task."),
                StudyPlanRevisionItem(cadence="Final 48 hours", activity="Review summaries and test the full goal end to end."),
            ],
            rationale=(
                "This fallback plan keeps scope small, orders topics from orientation to practice, "
                "and uses spaced retrieval so progress continues even without live AI generation."
            ),
        )

    def _unique_topic_title(self, title: str, seen_titles: set[str]) -> str:
        base_title = title[:150].rstrip() or "Selected material"
        candidate = base_title
        counter = 2
        while candidate.strip().lower() in seen_titles:
            suffix = f" ({counter})"
            candidate = f"{base_title[:160 - len(suffix)].rstrip()}{suffix}"
            counter += 1
        seen_titles.add(candidate.strip().lower())
        return candidate

    def _fallback_reason(self, exc: Exception) -> str:
        if isinstance(exc, AIProviderError):
            return exc.error_type
        if isinstance(exc, AIProviderConfigurationError):
            return "provider_not_configured"
        return "invalid_provider_response"
