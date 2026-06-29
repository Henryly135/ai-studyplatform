from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.uuid_codec import encode_course_uuid, encode_module_uuid
from app.models.modules import Module
from app.services.module_profile_initialization_client import ModuleProfileInitializationClient
from app.services.module_unlocking_service import ModuleUnlockingService


logger = logging.getLogger(__name__)


class ModuleProfileTriggerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.unlocking = ModuleUnlockingService(session)
        self.client = ModuleProfileInitializationClient()

    def initialize_currently_unlocked_for_enrollment(self, *, course_id: int, learner_id: int) -> None:
        modules = self.unlocking.list_unlocked_modules_for_learner(
            course_id=course_id,
            learner_id=learner_id,
        )
        self._initialize_modules(
            learner_id=learner_id,
            course_id=course_id,
            modules=modules,
            trigger_source="course_enrollment",
        )

    def initialize_newly_unlocked_after_completion(
        self,
        *,
        course_id: int,
        completed_module_id: int,
        learner_id: int,
    ) -> None:
        modules = self.unlocking.list_newly_unlocked_modules_after_completion(
            course_id=course_id,
            completed_module_id=completed_module_id,
            learner_id=learner_id,
        )
        self._initialize_modules(
            learner_id=learner_id,
            course_id=course_id,
            modules=modules,
            trigger_source="module_unlocked",
        )

    def _initialize_modules(
        self,
        *,
        learner_id: int,
        course_id: int,
        modules: list[Module],
        trigger_source: str,
    ) -> None:
        module_uuids = [encode_module_uuid(module.module_id) for module in modules]
        if not module_uuids:
            return

        try:
            self.client.initialize_modules(
                learner_id=learner_id,
                course_uuid=encode_course_uuid(course_id),
                module_uuids=module_uuids,
                trigger_source=trigger_source,
            )
        except Exception:
            logger.exception(
                "Failed to initialize module profiles for unlocked modules",
                extra={
                    "learnerId": learner_id,
                    "courseId": course_id,
                    "moduleUuids": module_uuids,
                    "triggerSource": trigger_source,
                },
            )
