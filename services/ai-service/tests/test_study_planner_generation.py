from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.services.providers.types import AIProviderError, ChatGenerationResult
from app.services.study_planner.generation_service import StudyPlanGenerationService
from app.services.study_planner.schemas import StudyPlanGenerationRequest


class FakeProvider:
    provider_name = "fake-provider"

    def __init__(self, *, text: str | None = None, error: Exception | None = None) -> None:
        self.text = text
        self.error = error

    def generate(self, request):
        if self.error:
            raise self.error
        assert request.response_mime_type == "application/json"
        return ChatGenerationResult(
            text=self.text,
            usage_metadata={"total_tokens": 12},
            raw_response={"ok": True},
        )


def _payload() -> StudyPlanGenerationRequest:
    return StudyPlanGenerationRequest(
        goal="Prepare for the algorithms final exam",
        availableMinutesPerWeek=360,
        targetDate="2026-08-15",
        preferences="Short weekday sessions and one longer weekend review.",
        materials=[
            {"title": "Sorting notes", "materialType": "pdf", "notes": "Week 1"},
            {"title": "Graph practice", "materialType": "link", "notes": "Tutorial set"},
        ],
    )


def test_study_plan_generation_uses_provider_json(monkeypatch) -> None:
    plan_json = {
        "overview": "A focused four week plan.",
        "weeklyCommitmentMinutes": 360,
        "phases": [
            {
                "title": "Foundation",
                "focus": "Review core algorithms.",
                "durationDays": 7,
                "outcomes": ["Sorting recall"],
            }
        ],
        "topics": [
            {"title": "Sorting", "reason": "It appears frequently.", "materials": ["Sorting notes"]},
            {"title": "Graphs", "reason": "It is a high-value exam area.", "materials": ["Graph practice"]},
        ],
        "revisionSchedule": [{"cadence": "Weekly", "activity": "Timed mixed practice."}],
        "rationale": "The plan starts with foundations and increases retrieval practice.",
    }
    monkeypatch.setattr(
        "app.services.study_planner.generation_service.get_chat_provider",
        lambda: FakeProvider(text=json.dumps(plan_json)),
    )

    result = StudyPlanGenerationService().generate(_payload())

    assert result.usedFallback is False
    assert result.provider == "fake-provider"
    assert result.planContent.topics[0].title == "Sorting"
    assert result.usageMetadata == {"total_tokens": 12}


def test_study_plan_generation_falls_back_when_provider_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.study_planner.generation_service.get_chat_provider",
        lambda: FakeProvider(error=AIProviderError("quota", error_type="quota", status_code=429)),
    )

    result = StudyPlanGenerationService().generate(_payload())

    assert result.usedFallback is True
    assert result.provider == "fallback"
    assert result.fallbackReason == "quota"
    assert result.planContent.weeklyCommitmentMinutes == 360
    assert [topic.title for topic in result.planContent.topics] == ["Sorting notes", "Graph practice"]


def test_study_plan_generation_fallback_deduplicates_material_titles(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.study_planner.generation_service.get_chat_provider",
        lambda: FakeProvider(error=AIProviderError("timeout", error_type="provider_timeout", status_code=408)),
    )
    payload = StudyPlanGenerationRequest(
        goal="Prepare for the algorithms final exam",
        availableMinutesPerWeek=360,
        materials=[
            {"title": "Sorting notes"},
            {"title": "Sorting notes"},
            {"title": " sorting notes "},
        ],
    )

    result = StudyPlanGenerationService().generate(payload)

    assert result.usedFallback is True
    assert [topic.title for topic in result.planContent.topics] == [
        "Sorting notes",
        "Sorting notes (2)",
        "sorting notes (3)",
    ]


def test_study_plan_generation_input_validation() -> None:
    with pytest.raises(ValidationError):
        StudyPlanGenerationRequest(goal="     ", availableMinutesPerWeek=360)

    with pytest.raises(ValidationError):
        StudyPlanGenerationRequest(
            goal="Prepare for the algorithms final exam",
            availableMinutesPerWeek=360,
            targetDate="soon",
        )

    with pytest.raises(ValidationError):
        StudyPlanGenerationRequest(
            goal="Prepare for the algorithms final exam",
            availableMinutesPerWeek=360,
            materials=[{"title": "   "}],
        )

    payload = StudyPlanGenerationRequest(
        goal="  Prepare for the algorithms final exam  ",
        availableMinutesPerWeek=360,
        targetDate="2026-08-15",
        materials=[{"title": "  Sorting notes  "}],
    )

    assert payload.goal == "Prepare for the algorithms final exam"
    assert payload.targetDate.isoformat() == "2026-08-15"
    assert payload.materials[0].title == "Sorting notes"
