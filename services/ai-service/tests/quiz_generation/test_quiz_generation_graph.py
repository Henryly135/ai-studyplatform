from __future__ import annotations

from app.services.orchestration.langgraph.quiz_generation_graph import QuizGenerationGraphRunner
from app.services.workflows.quiz_generation.schemas import (
    CreatedQuizQuestionRead,
    QuizGenerationCandidateSetRead,
    QuizGenerationContextRead,
    QuizGenerationPlanQuestionRead,
    QuizGenerationPlanRead,
    QuizGenerationRequest,
    RetrievalContextRead,
)


def test_quiz_generation_graph_runner(monkeypatch):
    # Tests quiz generation graph orchestrates load, retrieve, plan, generate, and publish steps.
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.nodes.load_inputs.QuizGenerationInputService.load_context",
        lambda self, payload: QuizGenerationContextRead(
            courseId=11,
            moduleId=22,
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            courseTitle="Pointers 101",
            moduleTitle="Memory Ownership",
            quizId=33,
            quizUuid="quiz-uuid",
            quizTitle="Ownership Quiz",
            quizDescription=None,
            quizStatus="published",
            questionCountPerAttempt=1,
            timeLimitSeconds=600,
            shuffleQuestions=True,
            shuffleOptions=False,
            availableQuestionCount=4,
        ),
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.nodes.retrieve_context.QuizGenerationRetrievalService.load_context",
        lambda self, **_: RetrievalContextRead(
            usedRetrieval=True,
            queryText="Generate 1 question",
            topK=5,
            chunkCount=1,
            chunks=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.nodes.plan_quiz.QuizGenerationPlanningService.build_plan",
        lambda self, **_: QuizGenerationPlanRead(
            titleSuggestion="Ownership Quiz",
            overview="Cover ownership basics",
            plannedQuestionCount=1,
            questions=[
                QuizGenerationPlanQuestionRead(
                    sortOrder=1,
                    learningObjective="Ownership basics",
                    difficulty="easy",
                    questionStyle="multiple_choice",
                    rationale="core concept",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.nodes.generate_quiz.QuizCandidateGenerationService.generate_candidates",
        lambda self, **_: QuizGenerationCandidateSetRead(
            questionCount=1,
            questions=[
                {
                    "questionText": "Which statement is correct?",
                    "explanationText": "Because ownership matters",
                    "sourceGrounding": "Memory Ownership notes, ownership basics.",
                    "sortOrder": 1,
                    "isActive": True,
                    "options": [
                        {"optionLabel": "A", "optionText": "Correct", "sortOrder": 1, "isCorrect": True},
                        {"optionLabel": "B", "optionText": "Wrong", "sortOrder": 2, "isCorrect": False},
                    ],
                }
            ],
        ),
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.nodes.publish_quiz.QuizGenerationPublishingService.publish_generated_questions",
        lambda self, **_: [CreatedQuizQuestionRead(questionId=1001, questionUuid="qq-1", sortOrder=5)],
    )

    result = QuizGenerationGraphRunner(session=object()).run(
        payload=QuizGenerationRequest(
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            educatorId=7,
            additionalInstructions="Focus on ownership.",
        )
    )

    assert result.context.quizId == 33
    assert result.candidateSet.questionCount == 1
    assert result.createdQuestions[0].questionId == 1001
