from __future__ import annotations

from app.schemas.profiles import ModuleProfileRead
from app.services.workflows.profile_update.schemas import (
    ModuleProfileCandidateUpdateResponse,
    ModuleProfileUpdateCheckDecision,
    ModuleProfileUpdateCheckResponse,
    ModuleUpdateContextResponse,
)


def _context_response() -> ModuleUpdateContextResponse:
    return ModuleUpdateContextResponse.model_validate(
        {
            "scope": {"learnerId": 7, "courseUuid": "course-uuid", "moduleUuid": "module-uuid"},
            "trigger": {"source": "quiz", "reason": "quiz_submitted"},
            "baseProfile": {
                "profileExists": False,
                "baseProfileSource": "default",
                "currentProfile": {"confidence_estimate": 0.5},
            },
            "quizSignalSummary": {
                "source": "quiz",
                "available": False,
                "unavailableReason": "learning_service_unavailable",
                "signalStrength": "none",
                "evidenceCount": 0,
                "timeWindow": None,
                "summary": None,
            },
            "chatSignalSummary": {
                "source": "chat",
                "available": False,
                "unavailableReason": "no_chat_sessions",
                "signalStrength": "none",
                "evidenceCount": 0,
                "timeWindow": None,
                "summary": None,
            },
            "recentHistorySummary": {
                "hasPriorActiveProfile": False,
                "latestVersion": None,
                "latestUpdatedAt": None,
                "latestProfileStatus": "default_only",
            },
            "updateConstraints": {
                "allowedPatchFields": ["weak_points"],
                "disallowedFields": ["version"],
                "updateModes": [{"mode": "no_update", "description": "Keep profile"}],
                "patchGuidance": ["Submit a patch"],
                "numericConstraints": [{"field": "confidence_estimate", "minValue": 0.0, "maxValue": 1.0}],
                "listConstraints": [{"field": "weak_points", "maxItems": 10, "maxItemLength": 300}],
            },
            "expectedAction": {
                "submissionType": "patch",
                "steps": ["Review base profile"],
                "outputShape": {"should_update": False, "update_mode": None, "reason": "string", "patch": {}},
            },
        }
    )


def test_context_candidate_and_run_check_endpoints(client, monkeypatch):
    # Tests internal profile update context, candidate, and run-check endpoints.
    from app.services.orchestration.langgraph.profile_update_graph import ModuleProfileUpdateGraphRunner
    from app.services.workflows.profile_update.services.candidate_service import ModuleProfileCandidateService
    from app.services.workflows.profile_update.services.context_service import ModuleUpdateContextService

    monkeypatch.setattr(ModuleUpdateContextService, "build_context", lambda self, payload: _context_response())
    monkeypatch.setattr(
        ModuleProfileCandidateService,
        "submit_candidate_patch",
        lambda self, payload: ModuleProfileCandidateUpdateResponse(
            accepted=True,
            retryable=False,
            code="PROFILE_UPDATED",
            message="Candidate patch accepted and persisted",
            changedFields=["confidence_estimate"],
            profile=ModuleProfileRead(
                learnerId=7,
                courseUuid="course-uuid",
                moduleUuid="module-uuid",
                version=1,
                objectKey="module/7/11/22/profile_v1.json",
                content={"confidence_estimate": 0.4},
                isDefaultProfile=False,
            ),
        ),
    )
    monkeypatch.setattr(
        ModuleProfileUpdateGraphRunner,
        "run",
        lambda self, payload, config=None: ModuleProfileUpdateCheckResponse(
            decision=ModuleProfileUpdateCheckDecision(
                should_update=False,
                update_mode=None,
                reason="No meaningful change",
                patch={},
            ),
            candidateResult=None,
        ),
    )

    context_response = client.post(
        "/internal/profile-update/context",
        json={
            "learnerId": 7,
            "courseUuid": "course-uuid",
            "moduleUuid": "module-uuid",
            "triggerSource": "quiz",
        },
    )
    assert context_response.status_code == 200
    assert context_response.json()["baseProfile"]["baseProfileSource"] == "default"

    candidate_response = client.post(
        "/internal/profile-update/candidate",
        json={
            "learnerId": 7,
            "courseUuid": "course-uuid",
            "moduleUuid": "module-uuid",
            "source": "quiz",
            "updateMode": "light_update",
            "reason": "quiz update",
            "patch": {"confidence_estimate": 0.4},
        },
    )
    assert candidate_response.status_code == 200
    assert candidate_response.json()["accepted"] is True

    run_check_response = client.post(
        "/internal/profile-update/run-check",
        json={
            "learnerId": 7,
            "courseUuid": "course-uuid",
            "moduleUuid": "module-uuid",
            "triggerSource": "chat",
        },
    )
    assert run_check_response.status_code == 200
    assert run_check_response.json()["decision"]["should_update"] is False
