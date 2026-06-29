from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from app.models.module_progress import ProgressStatus
from app.models.modules import Module, ModuleStatus
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_prerequisite_repository import ModulePrerequisiteRepository
from app.repositories.module_progress_repository import ModuleProgressRepository
from app.repositories.module_repository import ModuleRepository
from platform_common.errors import http_error


class ModuleUnlockingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.module_prerequisites = ModulePrerequisiteRepository(session)
        self.module_progress = ModuleProgressRepository(session)

    def is_module_unlocked(self, *, module_id: int, learner_id: int) -> bool:
        rule = self.module_prerequisites.get_by_module_id(module_id)
        if rule is None:
            return True

        progress = self.module_progress.get_by_module_and_learner(
            rule.prerequisite_module_id,
            learner_id,
        )
        return progress is not None and progress.progress_status == ProgressStatus.COMPLETED

    def ensure_module_unlocked(
        self,
        *,
        module_id: int,
        learner_id: int,
        resource_name: str = "module",
    ) -> None:
        if self.is_module_unlocked(module_id=module_id, learner_id=learner_id):
            return

        rule = self.module_prerequisites.get_by_module_id(module_id)
        prerequisite_module = self.modules.get_by_id(rule.prerequisite_module_id) if rule is not None else None
        prerequisite_title = prerequisite_module.title if prerequisite_module is not None else "the prerequisite module"
        raise http_error(
            status_code=status.HTTP_423_LOCKED,
            code="MODULE_LOCKED",
            message=f"Complete {prerequisite_title} before accessing this {resource_name}",
        )

    def list_unlocked_modules_for_learner(self, *, course_id: int, learner_id: int) -> list[Module]:
        learning_path = self.learning_paths.get_by_course_id(course_id)
        if learning_path is None:
            return []

        modules = self.modules.list_published_by_learning_path(learning_path.learning_path_id)
        return [
            module
            for module in modules
            if self.is_module_unlocked(module_id=module.module_id, learner_id=learner_id)
        ]

    def list_newly_unlocked_modules_after_completion(
        self,
        *,
        course_id: int,
        completed_module_id: int,
        learner_id: int,
    ) -> list[Module]:
        learning_path = self.learning_paths.get_by_course_id(course_id)
        if learning_path is None:
            return []

        modules = self.modules.list_published_by_learning_path(learning_path.learning_path_id)
        newly_unlocked: list[Module] = []
        for module in modules:
            if module.module_id == completed_module_id or module.status != ModuleStatus.PUBLISHED:
                continue
            rule = self.module_prerequisites.get_by_module_id(module.module_id)
            if rule is None or rule.prerequisite_module_id != completed_module_id:
                continue
            if self.is_module_unlocked(module_id=module.module_id, learner_id=learner_id):
                newly_unlocked.append(module)
        return newly_unlocked
