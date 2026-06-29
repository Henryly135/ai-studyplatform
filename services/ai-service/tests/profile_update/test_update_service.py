from __future__ import annotations

from dataclasses import dataclass

from app.schemas.profiles import ModuleProfileRead
from app.services.workflows.profile_update.schemas import ModuleProfileCandidateUpdateRequest, ModuleProfilePatch
from app.services.workflows.profile_update.services.candidate_service import ModuleProfileCandidateService
from app.services.workflows.profile_update.services.persistence_service import LoadedModuleProfileBase


@dataclass
class FakeSession:
    rollback_calls: int = 0
    commit_calls: int = 0
    refresh_calls: int = 0

    def rollback(self) -> None:
        self.rollback_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1

    def refresh(self, _obj) -> None:
        self.refresh_calls += 1


def _base_profile() -> dict:
    return {
        "profile_type": "module_profile",
        "profile_status": "initialized",
        "learning_style": "unknown",
        "response_preference": "adaptive",
        "knowledge_stability": "unknown",
        "engagement_pattern": "unknown",
        "common_error_patterns": [],
        "support_need_level": "medium",
        "confidence_estimate": 0.5,
        "weak_points": [],
        "strong_points": [],
        "recent_confusions": [],
        "recommended_focus": [],
    }


def test_submit_candidate_patch_accepts_valid_patch(monkeypatch):
    # Tests valid module profile candidate patches are accepted and persisted.
    session = FakeSession()
    service = ModuleProfileCandidateService(session=session)
    monkeypatch.setattr(
        service.persistence,
        "load_active_or_default",
        lambda **_: LoadedModuleProfileBase(
            course_id=11,
            module_id=22,
            active_asset=None,
            base_profile=_base_profile(),
        ),
    )
    monkeypatch.setattr(
        service.persistence,
        "persist_candidate",
        lambda **_: ModuleProfileRead(
            learnerId=7,
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            version=1,
            objectKey="module/7/11/22/profile_v1.json",
            content=_base_profile(),
            isDefaultProfile=False,
        ),
    )

    payload = ModuleProfileCandidateUpdateRequest(
        learnerId=7,
        courseUuid="course-uuid",
        moduleUuid="module-uuid",
        source="quiz",
        updateMode="light_update",
        reason="Quiz evidence shows a new weak point",
        patch=ModuleProfilePatch(
            weak_points=["pointer arithmetic"],
            recommended_focus=["trace pointers"],
            confidence_estimate=0.42,
        ),
    )

    result = service.submit_candidate_patch(payload=payload)

    assert result.accepted is True
    assert result.code == "PROFILE_UPDATED"
    assert result.profile is not None
    assert set(result.changedFields) == {"weak_points", "recommended_focus", "confidence_estimate"}


def test_submit_candidate_patch_rejects_invalid_candidate(monkeypatch):
    # Tests invalid module profile candidate patches are rejected and rolled back.
    session = FakeSession()
    service = ModuleProfileCandidateService(session=session)
    monkeypatch.setattr(
        service.persistence,
        "load_active_or_default",
        lambda **_: LoadedModuleProfileBase(
            course_id=11,
            module_id=22,
            active_asset=None,
            base_profile=_base_profile(),
        ),
    )

    payload = ModuleProfileCandidateUpdateRequest(
        learnerId=7,
        courseUuid="course-uuid",
        moduleUuid="module-uuid",
        source="quiz",
        updateMode="light_update",
        reason="Invalid candidate for validation test",
        patch=ModuleProfilePatch(
            response_preference="not_allowed",
            confidence_estimate=0.42,
        ),
    )

    result = service.submit_candidate_patch(payload=payload)

    assert result.accepted is False
    assert result.retryable is True
    assert result.code == "INVALID_CANDIDATE_PATCH"
    assert session.rollback_calls == 1
