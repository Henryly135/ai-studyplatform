from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.schemas.profiles import GlobalProfileRead, ModuleProfileRead
from app.services.workflows.quiz_generation.schemas import (
    QuizGenerationCandidateQuestion,
    QuizGenerationCandidateSetRead,
    QuizGenerationContextRead,
    QuizGenerationPlanQuestionRead,
    QuizGenerationPlanRead,
    QuizGenerationProfileContextRead,
    QuizGenerationRequest,
    RetrievalContextRead,
)
from app.services.workflows.quiz_generation.services.generation_service import QuizCandidateGenerationService
from app.services.workflows.quiz_generation.services.planning_service import QuizGenerationPlanningService
from app.services.workflows.quiz_generation.services.validation_service import QuizGenerationValidationService


def _request() -> QuizGenerationRequest:
    return QuizGenerationRequest(courseUuid="course-uuid", moduleUuid="module-uuid", educatorId=7, learnerId=8)


def _context() -> QuizGenerationContextRead:
    return QuizGenerationContextRead(
        courseId=11,
        moduleId=22,
        courseUuid="course-uuid",
        moduleUuid="module-uuid",
        courseTitle="Course",
        moduleTitle="Module",
        quizId=33,
        quizUuid="quiz-uuid",
        quizTitle="Quiz",
        quizDescription=None,
        quizStatus="published",
        questionCountPerAttempt=1,
        timeLimitSeconds=600,
        shuffleQuestions=True,
        shuffleOptions=False,
        availableQuestionCount=4,
    )


def _retrieval_context() -> RetrievalContextRead:
    return RetrievalContextRead(usedRetrieval=False, queryText="query", topK=5, chunkCount=0, chunks=[])


def _profile_context() -> QuizGenerationProfileContextRead:
    return QuizGenerationProfileContextRead(
        learnerId=8,
        globalProfile=GlobalProfileRead(learnerId=8, content="# Profile", isDefaultProfile=True),
        moduleProfile=ModuleProfileRead(
            learnerId=8,
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            content={"confidence_estimate": 0.5},
            isDefaultProfile=True,
        ),
    )


def test_validate_candidate_set_normalizes_options_and_text() -> None:
    # Tests candidate validation trims text, labels options, and forces active questions.
    candidate_set = QuizGenerationCandidateSetRead(
        questionCount=1,
        questions=[
            QuizGenerationCandidateQuestion(
                questionText="  Question?  ",
                explanationText="  Because. ",
                sourceGrounding="  Module notes, chunk 1. ",
                sortOrder=2,
                isActive=False,
                options=[
                    {"optionText": "  Correct  ", "sortOrder": 9, "isCorrect": True},
                    {"optionText": " Wrong ", "sortOrder": 8, "isCorrect": False},
                ],
            )
        ],
    )

    result = QuizGenerationValidationService().validate_candidate_set(
        candidate_set=candidate_set,
        required_question_count=1,
    )

    question = result.questions[0]
    assert question.questionText == "Question?"
    assert question.explanationText == "Because."
    assert question.sourceGrounding == "Module notes, chunk 1."
    assert question.isActive is True
    assert [option.optionLabel for option in question.options] == ["A", "B"]
    assert [option.sortOrder for option in question.options] == [1, 2]


@pytest.mark.parametrize("candidate_set", [SimpleNamespace(questionCount=2, questions=[]), SimpleNamespace(questionCount=1, questions=[])])
def test_validate_candidate_set_rejects_count_mismatch(candidate_set) -> None:
    # Tests candidate validation rejects mismatched declared/list question counts.
    with pytest.raises(Exception):
        QuizGenerationValidationService().validate_candidate_set(
            candidate_set=candidate_set,
            required_question_count=1,
        )


def test_planning_service_build_prompt_includes_profile_and_output_shape() -> None:
    # Tests planning prompt includes request, context, retrieval, profile, and schema guidance.
    prompt = QuizGenerationPlanningService()._build_prompt(
        request=_request(),
        context=_context(),
        retrieval_context=_retrieval_context(),
        profile_context=_profile_context(),
    )

    assert "Quiz generation request JSON" in prompt
    assert '"learnerId": 8' in prompt
    assert "Required output JSON shape" in prompt
    assert "plannedQuestionCount" in prompt


def test_candidate_generation_service_build_prompt_includes_plan_and_output_shape() -> None:
    # Tests candidate prompt includes the approved plan and required candidate JSON shape.
    plan = QuizGenerationPlanRead(
        titleSuggestion="Quiz",
        overview="Overview",
        plannedQuestionCount=1,
        questions=[
            QuizGenerationPlanQuestionRead(
                sortOrder=1,
                learningObjective="Objective",
                difficulty="easy",
                questionStyle="multiple_choice",
                rationale="Reason",
            )
        ],
    )

    prompt = QuizCandidateGenerationService()._build_prompt(
        request=_request(),
        context=_context(),
        retrieval_context=_retrieval_context(),
        plan=plan,
        profile_context=None,
    )

    assert "Approved quiz plan JSON" in prompt
    assert "learner_profile_context_not_requested" in prompt
    assert "questionCount" in prompt
    assert "sourceGrounding" in prompt


def test_candidate_question_requires_source_grounding() -> None:
    # Tests generated questions must include concise source grounding metadata.
    with pytest.raises(Exception):
        QuizGenerationCandidateQuestion.model_validate(
            {
                "questionText": "Question?",
                "explanationText": "Because.",
                "sortOrder": 1,
                "isActive": True,
                "options": [
                    {"optionText": "Correct", "sortOrder": 1, "isCorrect": True},
                    {"optionText": "Wrong", "sortOrder": 2, "isCorrect": False},
                ],
            }
        )


def test_profile_context_payload_marks_absent_or_present_profiles() -> None:
    # Tests profile context payload helpers for absent and present learner profiles.
    planning_service = QuizGenerationPlanningService()
    generation_service = QuizCandidateGenerationService()

    assert planning_service._profile_context_payload(None) == {
        "available": False,
        "reason": "learner_profile_context_not_requested",
    }
    assert generation_service._profile_context_payload(_profile_context())["available"] is True
