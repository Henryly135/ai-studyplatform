from __future__ import annotations

from app.services.orchestration.langgraph.generated_quiz_attempt_graph import GeneratedQuizAttemptGraphRunner
from app.services.workflows.quiz_generation.schemas import (
    CreatedQuizQuestionRead,
    QuizGeneratedAttemptStartResponse,
    QuizGenerationAutoStartRunRequest,
    QuizGenerationCandidateSetRead,
    QuizGenerationContextRead,
    QuizGenerationPlanQuestionRead,
    QuizGenerationPlanRead,
    QuizGenerationRunResponse,
    RetrievalContextRead,
)


def _generation_response() -> QuizGenerationRunResponse:
    return QuizGenerationRunResponse(
        context=QuizGenerationContextRead(
            courseId=11,
            moduleId=22,
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            courseTitle="Pointers 101",
            moduleTitle="Memory Ownership",
            quizId=33,
            quizUuid="quiz-uuid",
            quizTitle="Ownership Quiz",
            quizDescription="ownership basics",
            quizStatus="published",
            questionCountPerAttempt=2,
            timeLimitSeconds=600,
            shuffleQuestions=True,
            shuffleOptions=False,
            availableQuestionCount=4,
        ),
        retrievalContext=RetrievalContextRead(
            usedRetrieval=True,
            queryText="Generate 2 questions",
            topK=5,
            chunkCount=1,
            chunks=[],
            chatModelId="glm:glm-4.7",
            embeddingModelId="glm:embedding-3",
            embeddingVersion="glm:embedding-3@1024",
            indexStatus="ready",
            indexCoverage=1.0,
        ),
        plan=QuizGenerationPlanRead(
            titleSuggestion="Ownership Quiz",
            overview="Cover ownership basics",
            plannedQuestionCount=2,
            questions=[
                QuizGenerationPlanQuestionRead(
                    sortOrder=1,
                    learningObjective="Ownership basics",
                    difficulty="easy",
                    questionStyle="multiple_choice",
                    rationale="core concept",
                ),
                QuizGenerationPlanQuestionRead(
                    sortOrder=2,
                    learningObjective="Heap vs stack",
                    difficulty="medium",
                    questionStyle="true_false",
                    rationale="important distinction",
                ),
            ],
        ),
        candidateSet=QuizGenerationCandidateSetRead(
            questionCount=2,
            questions=[
                {
                    "questionText": "Which statement is correct?",
                    "explanationText": "Because ownership matters",
                    "sortOrder": 1,
                    "isActive": True,
                    "options": [
                        {"optionLabel": "A", "optionText": "Correct", "sortOrder": 1, "isCorrect": True},
                        {"optionLabel": "B", "optionText": "Wrong", "sortOrder": 2, "isCorrect": False},
                    ],
                },
                {
                    "questionText": "True or false?",
                    "explanationText": "Because heap and stack differ",
                    "sortOrder": 2,
                    "isActive": True,
                    "options": [
                        {"optionLabel": "A", "optionText": "True", "sortOrder": 1, "isCorrect": True},
                        {"optionLabel": "B", "optionText": "False", "sortOrder": 2, "isCorrect": False},
                    ],
                },
            ],
        ),
        createdQuestions=[
            CreatedQuizQuestionRead(questionId=1001, questionUuid="qq-1", sortOrder=5),
            CreatedQuizQuestionRead(questionId=1002, questionUuid="qq-2", sortOrder=6),
        ],
    )


def test_generated_quiz_attempt_graph_runner(monkeypatch):
    # Tests generated quiz attempt graph runs generation then starts an attempt.
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.nodes.run_generation_workflow.QuizGenerationGraphRunner.run",
        lambda self, payload: _generation_response(),
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.nodes.start_generated_attempt.LearningQuizGenerationClient.start_generated_attempt_internal",
        lambda self, **kwargs: QuizGeneratedAttemptStartResponse(
            quizId=33,
            quizUuid="quiz-uuid",
            moduleId=22,
            moduleUuid="module-uuid",
            attemptSessionToken="token-123",
            attemptNumber=1,
            questionCount=2,
            timeLimitSeconds=600,
            startedAt="2026-01-01T00:00:00Z",
            expiresAt="2026-01-01T00:10:00Z",
            questions=[],
        ),
    )

    result = GeneratedQuizAttemptGraphRunner(session=object()).run(
        payload=QuizGenerationAutoStartRunRequest(
            courseUuid="course-uuid",
            moduleUuid="module-uuid",
            actorId=77,
            additionalInstructions="Focus on ownership.",
        )
    )

    assert result.attemptSessionToken == "token-123"
    assert result.questionCount == 2
