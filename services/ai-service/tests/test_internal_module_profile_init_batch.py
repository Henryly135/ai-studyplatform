from __future__ import annotations

from app.schemas.profiles import ModuleProfileInitBatchResponse


def test_internal_module_profile_init_batch_endpoint(client, monkeypatch):
    # Tests the internal batch module profile init endpoint returns batch counts.
    from app.services.profiles.module_profile_service import ModuleProfileService

    def _fake_batch(self, payload):
        return ModuleProfileInitBatchResponse(
            learnerId=payload.learnerId,
            courseUuid=payload.courseUuid,
            triggerSource=payload.triggerSource,
            requestedCount=len(payload.moduleUuids),
            initializedCount=1,
            skippedCount=1,
            failedCount=0,
            failedItems=[],
        )

    monkeypatch.setattr(ModuleProfileService, "initialize_batch_for_learner", _fake_batch)

    response = client.post(
        "/internal/profiles/module/init-batch",
        json={
            "learnerId": 7,
            "courseUuid": "course-uuid",
            "moduleUuids": ["module-a", "module-b"],
            "triggerSource": "course_enrollment",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requestedCount"] == 2
    assert body["initializedCount"] == 1
    assert body["skippedCount"] == 1
