from __future__ import annotations

from app.core.uuid_codec import decode_course_uuid, decode_module_uuid
from app.services.workflows.quiz_generation.schemas import (
    EducatorQuizDraftGenerationRequest,
    EducatorQuizDraftGenerationResponse,
    QuizGenerationContextRead,
    QuizGenerationRequest,
)
from app.services.workflows.quiz_generation.services.generation_service import QuizCandidateGenerationService
from app.services.workflows.quiz_generation.services.planning_service import QuizGenerationPlanningService
from app.services.workflows.quiz_generation.services.retrieval_service import QuizGenerationRetrievalService
from app.services.workflows.quiz_generation.services.validation_service import QuizGenerationValidationService


class EducatorQuizDraftGenerationService:
    def __init__(self, session) -> None:
        self.session = session

    def generate_draft(self, payload: EducatorQuizDraftGenerationRequest) -> EducatorQuizDraftGenerationResponse:
        context = self._build_context(payload)
        request = QuizGenerationRequest(
            courseUuid=payload.courseUuid,
            moduleUuid=payload.moduleUuid,
            educatorId=payload.educatorId,
            learnerId=None,
            additionalInstructions=self._build_additional_instructions(payload),
        )
        retrieval_context = QuizGenerationRetrievalService(self.session).load_context(
            educator_id=payload.educatorId,
            course_uuid=payload.courseUuid,
            module_uuid=payload.moduleUuid,
            quiz_title=context.quizTitle,
            module_title=context.moduleTitle,
            question_count=context.questionCountPerAttempt,
            additional_instructions=request.additionalInstructions,
        )
        plan = QuizGenerationPlanningService().build_plan(
            request=request,
            context=context,
            retrieval_context=retrieval_context,
            profile_context=None,
        )
        candidate_set = QuizCandidateGenerationService().generate_candidates(
            request=request,
            context=context,
            retrieval_context=retrieval_context,
            plan=plan,
            profile_context=None,
        )
        candidate_set = QuizGenerationValidationService().validate_candidate_set(
            candidate_set=candidate_set,
            required_question_count=payload.questionCount,
        )
        return EducatorQuizDraftGenerationResponse(
            context=context,
            retrievalContext=retrieval_context,
            plan=plan,
            candidateSet=candidate_set,
        )

    def _build_context(self, payload: EducatorQuizDraftGenerationRequest) -> QuizGenerationContextRead:
        return QuizGenerationContextRead(
            courseId=decode_course_uuid(payload.courseUuid),
            moduleId=decode_module_uuid(payload.moduleUuid),
            courseUuid=payload.courseUuid,
            moduleUuid=payload.moduleUuid,
            courseTitle=payload.courseTitle,
            moduleTitle=payload.moduleTitle,
            quizId=1,
            quizUuid="draft",
            quizTitle=payload.quizTitle,
            quizDescription=None,
            quizStatus="draft",
            questionCountPerAttempt=payload.questionCount,
            timeLimitSeconds=payload.timeLimitSeconds,
            shuffleQuestions=payload.shuffleQuestions,
            shuffleOptions=payload.shuffleOptions,
            availableQuestionCount=payload.availableQuestionCount,
        )

    def _build_additional_instructions(self, payload: EducatorQuizDraftGenerationRequest) -> str:
        parts = [
            "Generate an educator-editable quiz draft. Do not assume it is published.",
            f"Difficulty target: {payload.difficulty}.",
            f"Question types allowed: {', '.join(payload.questionTypes)}.",
        ]
        if payload.learningObjectives:
            parts.append(f"Learning objectives: {'; '.join(payload.learningObjectives)}.")
        if payload.materialScope:
            parts.append(f"Material scope: {payload.materialScope}.")
        if payload.additionalInstructions:
            parts.append(f"Educator instructions: {payload.additionalInstructions}.")
        return " ".join(parts)
