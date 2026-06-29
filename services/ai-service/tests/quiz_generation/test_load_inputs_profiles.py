from __future__ import annotations

from app.schemas.profiles import GlobalProfileRead, ModuleProfileRead
from app.services.workflows.quiz_generation.schemas import QuizGenerationRequest
from app.services.workflows.quiz_generation.services.load_inputs_service import QuizGenerationInputService


def test_load_profile_context_reads_global_and_initializes_module_profile(monkeypatch):
    # Tests quiz generation profile context loads global profile and initializes module profile.
    calls: dict[str, object] = {}

    def _fake_get_global(self, learner_id):
        calls["globalLearnerId"] = learner_id
        return GlobalProfileRead(
            learnerId=learner_id,
            content="# Default global profile",
            isDefaultProfile=True,
        )

    def _fake_initialize_module(self, learner_id, course_uuid, module_uuid):
        calls["moduleArgs"] = {
            "learnerId": learner_id,
            "courseUuid": course_uuid,
            "moduleUuid": module_uuid,
        }
        return ModuleProfileRead(
            learnerId=learner_id,
            courseUuid=course_uuid,
            moduleUuid=module_uuid,
            version=1,
            objectKey="module/7/11/22/profile_v1.json",
            content={"confidence_estimate": 0.5},
            isDefaultProfile=False,
        )

    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.load_inputs_service.GlobalProfileService.get_for_learner",
        _fake_get_global,
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.load_inputs_service.ModuleProfileService.initialize_for_learner",
        _fake_initialize_module,
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.load_inputs_service.CommunicationNotificationClient.send_learning_profile_initialization_prompt",
        lambda self, learner_id: calls.setdefault("notificationLearnerId", learner_id),
    )

    profile_context = QuizGenerationInputService(session=object()).load_profile_context(
        payload=QuizGenerationRequest(
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            educatorId=7,
            learnerId=77,
        )
    )

    assert profile_context is not None
    assert profile_context.globalProfile.isDefaultProfile is True
    assert profile_context.moduleProfile.isDefaultProfile is False
    assert calls["globalLearnerId"] == 77
    assert calls["notificationLearnerId"] == 77
    assert calls["moduleArgs"] == {
        "learnerId": 77,
        "courseUuid": "course-uuid",
        "moduleUuid": "module-uuid",
    }


def test_load_profile_context_skips_when_generation_has_no_learner():
    # Tests quiz generation profile context is skipped when learnerId is absent.
    profile_context = QuizGenerationInputService(session=None).load_profile_context(
        payload=QuizGenerationRequest(
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            educatorId=7,
        )
    )

    assert profile_context is None
