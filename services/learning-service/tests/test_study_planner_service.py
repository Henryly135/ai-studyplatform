from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.study_plans import StudyPlan, StudyPlanStatus
from app.repositories.study_plan_repository import StudyPlanRepository
from app.schemas.study_planner import StudyPlanCreateRequest, StudyPlanUpdateRequest
from app.services.study_planner_service import StudyPlannerService


class FakeSession:
    def __init__(self, *, scalar_result=None, scalars_result=None):
        self.scalar_result = scalar_result
        self.scalars_result = scalars_result or []
        self.added = []
        self.flushed = 0
        self.commits = 0

    def scalar(self, stmt):
        return self.scalar_result

    def scalars(self, stmt):
        return list(self.scalars_result)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed += 1
        now = datetime(2026, 6, 29, 12, 0, 0)
        for obj in self.added:
            if isinstance(obj, StudyPlan):
                if not obj.plan_id:
                    obj.plan_id = len(self.added)
                if not obj.plan_uuid:
                    obj.plan_uuid = str(uuid4())
                if not obj.created_at:
                    obj.created_at = now
                if not obj.updated_at:
                    obj.updated_at = now

    def commit(self):
        self.commits += 1


class FakeAIClient:
    def __init__(self, *, suffix: str = "initial", fallback: bool = False, invalid_response: bool = False) -> None:
        self.suffix = suffix
        self.fallback = fallback
        self.invalid_response = invalid_response
        self.calls = []

    def generate_plan(self, payload: StudyPlanCreateRequest):
        self.calls.append(payload)
        if self.invalid_response:
            return {
                "planContent": {"overview": "missing required fields"},
                "provider": "fake-ai",
                "model": "fake-model",
                "usedFallback": False,
            }
        return {
            "planContent": _plan_content(self.suffix),
            "provider": "fake-ai",
            "model": "fake-model",
            "usedFallback": self.fallback,
            "fallbackReason": "quota" if self.fallback else None,
        }


def _payload() -> StudyPlanCreateRequest:
    return StudyPlanCreateRequest(
        goal="Build a revision plan for COMP algorithms",
        availableMinutesPerWeek=300,
        materials=[{"title": "Lecture notes"}],
    )


def _plan_content(suffix: str = "initial"):
    return {
        "overview": f"Overview {suffix}",
        "weeklyCommitmentMinutes": 300,
        "phases": [
            {
                "title": "Map",
                "focus": "Find the important topics.",
                "durationDays": 3,
                "outcomes": ["Topic map"],
            }
        ],
        "topics": [
            {"title": f"Graphs {suffix}", "reason": "High-value topic.", "materials": ["Lecture notes"]}
        ],
        "revisionSchedule": [{"cadence": "Weekly", "activity": "Timed recall."}],
        "rationale": "Start broad, then review.",
    }


def _plan(*, learner_id: int = 7, suffix: str = "saved") -> StudyPlan:
    plan = StudyPlan(
        plan_id=1,
        plan_uuid="plan-uuid",
        learner_id=learner_id,
        title="Saved plan",
        status=StudyPlanStatus.ACTIVE,
        input_json=_payload().model_dump(),
        plan_json=_plan_content(suffix),
        provider_name="fake-ai",
        provider_model="fake-model",
        used_fallback=False,
        fallback_reason=None,
        created_at=datetime(2026, 6, 29, 12, 0, 0),
        updated_at=datetime(2026, 6, 29, 12, 0, 0),
    )
    return plan


def test_study_plan_create_saves_ai_generation_and_can_be_read() -> None:
    session = FakeSession()
    ai_client = FakeAIClient()
    service = StudyPlannerService(session, ai_client=ai_client)

    created = service.create_plan(payload=_payload(), current_user={"id": 7, "identity": "Learner"})

    assert created.learnerId == 7
    assert created.status == "active"
    assert created.planContent.topics[0].title == "Graphs initial"
    assert created.generation.provider == "fake-ai"
    assert session.added[0].input_json["goal"] == "Build a revision plan for COMP algorithms"
    assert session.commits == 1

    session.scalar_result = session.added[0]
    loaded = service.get_plan(plan_uuid=created.planUuid, current_user={"id": 7, "identity": "Learner"})
    assert loaded.planUuid == created.planUuid


def test_study_plan_access_requires_learner_identity() -> None:
    service = StudyPlannerService(FakeSession(), ai_client=FakeAIClient())

    with pytest.raises(HTTPException) as exc_info:
        service.list_plans(current_user={"id": 9, "identity": "Educator"})

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "LEARNER_REQUIRED"


def test_study_plan_create_input_validation() -> None:
    with pytest.raises(ValidationError):
        StudyPlanCreateRequest(goal="bad", availableMinutesPerWeek=5)

    with pytest.raises(ValidationError):
        StudyPlanCreateRequest(goal="     ", availableMinutesPerWeek=300)

    with pytest.raises(ValidationError):
        StudyPlanCreateRequest(
            goal="Build a revision plan for COMP algorithms",
            availableMinutesPerWeek=300,
            targetDate="next Friday",
        )

    with pytest.raises(ValidationError):
        StudyPlanCreateRequest(
            goal="Build a revision plan for COMP algorithms",
            availableMinutesPerWeek=300,
            materials=[{"title": "   "}],
        )

    payload = StudyPlanCreateRequest(
        goal="   Build a revision plan for COMP algorithms   ",
        availableMinutesPerWeek=300,
        targetDate="2026-08-15",
        materials=[{"title": "   Lecture notes   "}],
    )
    assert payload.goal == "Build a revision plan for COMP algorithms"
    assert payload.targetDate.isoformat() == "2026-08-15"
    assert payload.materials[0].title == "Lecture notes"

    with pytest.raises(ValidationError):
        StudyPlanUpdateRequest()


def test_study_plan_owner_isolation_returns_not_found() -> None:
    service = StudyPlannerService(FakeSession(scalar_result=_plan(learner_id=7)), ai_client=FakeAIClient())

    with pytest.raises(HTTPException) as exc_info:
        service.get_plan(plan_uuid="plan-uuid", current_user={"id": 8, "identity": "Learner"})

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "STUDY_PLAN_NOT_FOUND"


def test_study_plan_invalid_ai_response_maps_to_bad_gateway() -> None:
    service = StudyPlannerService(FakeSession(), ai_client=FakeAIClient(invalid_response=True))

    with pytest.raises(HTTPException) as exc_info:
        service.create_plan(payload=_payload(), current_user={"id": 7, "identity": "Learner"})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["code"] == "INVALID_AI_STUDY_PLAN_RESPONSE"


def test_study_plan_update_and_regenerate() -> None:
    plan = _plan()
    plan.adjustment_notes = "Old note"
    session = FakeSession(scalar_result=plan, scalars_result=[plan])
    service = StudyPlannerService(session, ai_client=FakeAIClient(suffix="regen", fallback=True))

    updated = service.update_plan(
        plan_uuid="plan-uuid",
        payload=StudyPlanUpdateRequest(title="Adjusted", adjustmentNotes="Moved graph practice earlier."),
        current_user={"id": 7, "identity": "Learner"},
    )
    assert updated.title == "Adjusted"
    assert updated.adjustmentNotes == "Moved graph practice earlier."

    cleared = service.update_plan(
        plan_uuid="plan-uuid",
        payload=StudyPlanUpdateRequest(adjustmentNotes=None),
        current_user={"id": 7, "identity": "Learner"},
    )
    assert cleared.adjustmentNotes is None

    regenerated = service.regenerate_plan(plan_uuid="plan-uuid", current_user={"id": 7, "identity": "Learner"})
    assert regenerated.planContent.topics[0].title == "Graphs regen"
    assert regenerated.generation.usedFallback is True
    assert regenerated.generation.fallbackReason == "quota"
    assert session.commits == 3


def test_study_plan_repository_lists_and_updates() -> None:
    plan = SimpleNamespace(
        plan_uuid="plan-uuid",
        learner_id=7,
        title="Old",
        status=StudyPlanStatus.ACTIVE,
        plan_json=_plan_content(),
        provider_name="old",
        provider_model="old-model",
        used_fallback=False,
        fallback_reason=None,
        adjustment_notes=None,
    )
    session = FakeSession(scalar_result=plan, scalars_result=[plan])
    repo = StudyPlanRepository(session)

    assert repo.get_by_uuid("plan-uuid") is plan
    assert repo.list_by_learner(7) == [plan]

    repo.update(
        plan,
        title="New",
        status=StudyPlanStatus.ARCHIVED,
        used_fallback=True,
        fallback_reason="quota",
    )

    assert plan.title == "New"
    assert plan.status == StudyPlanStatus.ARCHIVED
    assert plan.used_fallback is True
    assert session.flushed == 1
