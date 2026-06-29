from __future__ import annotations

import logging

from app.services.communication_notification_client import CommunicationNotificationClient
from app.services.profiles.global_profile_service import GlobalProfileService
from app.services.profiles.module_profile_service import ModuleProfileService
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationContextRead,
    QuizGenerationProfileContextRead,
    QuizGenerationRequest,
)
from app.services.workflows.quiz_generation.services.learning_quiz_generation_client import LearningQuizGenerationClient


logger = logging.getLogger(__name__)


class QuizGenerationInputService:
    def __init__(self, session=None) -> None:
        self.session = session
        self.learning = LearningQuizGenerationClient()

    def load_context(self, *, payload: QuizGenerationRequest) -> QuizGenerationContextRead:
        return self.learning.fetch_context(
            course_uuid=payload.courseUuid,
            module_uuid=payload.moduleUuid,
        )

    def load_profile_context(self, *, payload: QuizGenerationRequest) -> QuizGenerationProfileContextRead | None:
        if payload.learnerId is None:
            return None
        if self.session is None:
            raise ValueError("A database session is required to load learner profile context")

        global_profile = GlobalProfileService(self.session).get_for_learner(learner_id=payload.learnerId)
        if global_profile.isDefaultProfile:
            self._send_learning_profile_prompt(learner_id=payload.learnerId)
        module_profile = ModuleProfileService(self.session).initialize_for_learner(
            learner_id=payload.learnerId,
            course_uuid=payload.courseUuid,
            module_uuid=payload.moduleUuid,
        )
        return QuizGenerationProfileContextRead(
            learnerId=payload.learnerId,
            globalProfile=global_profile,
            moduleProfile=module_profile,
        )

    def _send_learning_profile_prompt(self, *, learner_id: int) -> None:
        try:
            CommunicationNotificationClient().send_learning_profile_initialization_prompt(
                learner_id=learner_id,
            )
        except Exception:
            logger.exception(
                "Failed to send learning profile initialization notification",
                extra={"learnerId": learner_id},
            )
