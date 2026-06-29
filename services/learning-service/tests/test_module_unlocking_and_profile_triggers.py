from __future__ import annotations

from dataclasses import dataclass

from app.models.module_progress import ProgressStatus
from app.models.modules import ModuleStatus
from app.services.module_profile_trigger_service import ModuleProfileTriggerService
from app.services.module_unlocking_service import ModuleUnlockingService


@dataclass
class FakeLearningPath:
    learning_path_id: int


@dataclass
class FakeModule:
    module_id: int
    title: str
    status: ModuleStatus = ModuleStatus.PUBLISHED


@dataclass
class FakeRule:
    module_id: int
    prerequisite_module_id: int


@dataclass
class FakeProgress:
    progress_status: ProgressStatus


class FakeLearningPaths:
    def get_by_course_id(self, course_id: int):
        return FakeLearningPath(learning_path_id=course_id * 10)


class FakeModules:
    def __init__(self, modules: list[FakeModule]) -> None:
        self.modules = modules

    def list_published_by_learning_path(self, learning_path_id: int):
        return [module for module in self.modules if module.status == ModuleStatus.PUBLISHED]

    def get_by_id(self, module_id: int):
        return next((module for module in self.modules if module.module_id == module_id), None)


class FakePrerequisites:
    def __init__(self, rules: dict[int, int]) -> None:
        self.rules = rules

    def get_by_module_id(self, module_id: int):
        prerequisite_id = self.rules.get(module_id)
        if prerequisite_id is None:
            return None
        return FakeRule(module_id=module_id, prerequisite_module_id=prerequisite_id)


class FakeProgressRepo:
    def __init__(self, completed_module_ids: set[int]) -> None:
        self.completed_module_ids = completed_module_ids

    def get_by_module_and_learner(self, module_id: int, learner_id: int):
        if module_id not in self.completed_module_ids:
            return None
        return FakeProgress(progress_status=ProgressStatus.COMPLETED)


def _unlocking_service(*, completed_module_ids: set[int]) -> ModuleUnlockingService:
    service = ModuleUnlockingService(session=object())
    service.learning_paths = FakeLearningPaths()
    service.modules = FakeModules(
        [
            FakeModule(module_id=1, title="Intro"),
            FakeModule(module_id=2, title="Next"),
            FakeModule(module_id=3, title="Final"),
        ]
    )
    service.module_prerequisites = FakePrerequisites({2: 1, 3: 2})
    service.module_progress = FakeProgressRepo(completed_module_ids)
    return service


def test_list_unlocked_modules_for_learner_includes_only_satisfied_prerequisites():
    # Tests that learners only see published modules whose prerequisites are satisfied.
    service = _unlocking_service(completed_module_ids={1})

    unlocked = service.list_unlocked_modules_for_learner(course_id=10, learner_id=7)

    assert [module.module_id for module in unlocked] == [1, 2]


def test_list_newly_unlocked_modules_after_completion_returns_direct_unlocked_dependents():
    # Tests that completing a module returns newly unlocked dependent modules.
    service = _unlocking_service(completed_module_ids={1, 2})

    unlocked = service.list_newly_unlocked_modules_after_completion(
        course_id=10,
        completed_module_id=2,
        learner_id=7,
    )

    assert [module.module_id for module in unlocked] == [3]


def test_profile_trigger_initializes_currently_unlocked_modules(monkeypatch):
    # Tests that enrollment triggers profile initialization for currently unlocked modules.
    calls: list[dict[str, object]] = []
    trigger = ModuleProfileTriggerService(session=object())
    trigger.unlocking = _unlocking_service(completed_module_ids={1})

    monkeypatch.setattr(
        trigger.client,
        "initialize_modules",
        lambda **kwargs: calls.append(kwargs) or {"initializedCount": 2},
    )

    trigger.initialize_currently_unlocked_for_enrollment(course_id=10, learner_id=7)

    assert len(calls) == 1
    assert calls[0]["learner_id"] == 7
    assert calls[0]["trigger_source"] == "course_enrollment"
    assert len(calls[0]["module_uuids"]) == 2


def test_profile_trigger_swallows_ai_initialization_failure(monkeypatch):
    # Tests that profile initialization failures from AI service are swallowed.
    trigger = ModuleProfileTriggerService(session=object())
    trigger.unlocking = _unlocking_service(completed_module_ids={1})

    def _raise(**kwargs):
        raise RuntimeError("ai unavailable")

    monkeypatch.setattr(trigger.client, "initialize_modules", _raise)

    trigger.initialize_currently_unlocked_for_enrollment(course_id=10, learner_id=7)
