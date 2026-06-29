from __future__ import annotations

from types import SimpleNamespace

from app.services.orchestration.langgraph.profile_update_graph import ModuleProfileUpdateGraphRunner
from app.services.workflows.profile_update.schemas import (
    ModuleProfileCandidateUpdateResponse,
    ModuleProfileUpdateCheckDecision,
    ModuleProfileUpdateCheckRequest,
)
from app.schemas.profiles import ModuleProfileRead


class FakeContext:
    def __init__(self, payload: dict):
        self.payload = payload

    def model_dump(self, mode: str = "python"):
        return self.payload


def test_run_update_check_returns_no_update(monkeypatch):
    # Tests profile update graph returns no candidate when decision says no update.
    runner = ModuleProfileUpdateGraphRunner(session=object())
    monkeypatch.setattr(
        "app.services.workflows.profile_update.nodes.load_context.ModuleUpdateContextService.build_context",
        lambda self, payload: FakeContext({"scope": {"learnerId": 7}}),
    )
    monkeypatch.setattr(
        "app.services.workflows.profile_update.nodes.decide_update.ModuleProfileUpdateDecisionService.generate_decision",
        lambda self, **_: ModuleProfileUpdateCheckDecision(
            should_update=False,
            update_mode=None,
            reason="Signals are too weak",
            patch={},
        ),
    )

    result = runner.run(
        payload=ModuleProfileUpdateCheckRequest(
            learnerId=7,
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            triggerSource="quiz",
        )
    )

    assert result.decision.should_update is False
    assert result.candidateResult is None


def test_run_update_check_retries_once_then_succeeds(monkeypatch):
    # Tests profile update graph retries after a retryable invalid candidate.
    runner = ModuleProfileUpdateGraphRunner(session=object())
    monkeypatch.setattr(
        "app.services.workflows.profile_update.nodes.load_context.ModuleUpdateContextService.build_context",
        lambda self, payload: FakeContext({"scope": {"learnerId": 7}}),
    )

    decisions = iter(
        [
            ModuleProfileUpdateCheckDecision(
                should_update=True,
                update_mode="light_update",
                reason="Initial patch",
                patch={"confidence_estimate": 0.3, "weak_points": ["ownership"], "recommended_focus": ["trace memory"]},
            ),
            ModuleProfileUpdateCheckDecision(
                should_update=True,
                update_mode="light_update",
                reason="Corrected patch",
                patch={"confidence_estimate": 0.35, "weak_points": ["ownership"], "recommended_focus": ["trace memory"]},
            ),
        ]
    )
    monkeypatch.setattr(
        "app.services.workflows.profile_update.nodes.decide_update.ModuleProfileUpdateDecisionService.generate_decision",
        lambda self, **_: next(decisions),
    )

    results = iter(
        [
            ModuleProfileCandidateUpdateResponse(
                accepted=False,
                retryable=True,
                code="INVALID_CANDIDATE_PATCH",
                message="confidence_estimate must be between 0 and 1",
                changedFields=["confidence_estimate"],
                profile=None,
            ),
            ModuleProfileCandidateUpdateResponse(
                accepted=True,
                retryable=False,
                code="PROFILE_UPDATED",
                message="Candidate patch accepted and persisted",
                changedFields=["confidence_estimate", "weak_points", "recommended_focus"],
                profile=ModuleProfileRead(
                    learnerId=7,
                    courseUuid="course-uuid",
                    moduleUuid="module-uuid",
                    version=2,
                    objectKey="module/7/11/22/profile_v2.json",
                    content={"confidence_estimate": 0.35},
                    isDefaultProfile=False,
                ),
            ),
        ]
    )
    monkeypatch.setattr(
        "app.services.workflows.profile_update.nodes.submit_candidate.ModuleProfileCandidateService.submit_candidate_patch",
        lambda self, **_: next(results),
    )

    result = runner.run(
        payload=ModuleProfileUpdateCheckRequest(
            learnerId=7,
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            triggerSource="chat",
        )
    )

    assert result.decision.should_update is True
    assert result.candidateResult is not None
    assert result.candidateResult.accepted is True
    assert result.candidateResult.profile is not None
    assert result.candidateResult.profile.version == 2
