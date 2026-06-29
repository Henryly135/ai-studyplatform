from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import (
    CreatedQuizQuestionRead,
    QuizGenerationCandidateSetRead,
)
from app.services.workflows.quiz_generation.services.learning_quiz_generation_client import LearningQuizGenerationClient


class QuizGenerationPublishingService:
    def __init__(self) -> None:
        self.learning = LearningQuizGenerationClient()

    def publish_generated_questions(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        candidate_set: QuizGenerationCandidateSetRead,
    ) -> list[CreatedQuizQuestionRead]:
        return self.learning.batch_create_questions(
            course_uuid=course_uuid,
            module_uuid=module_uuid,
            candidate_set=candidate_set,
        )
