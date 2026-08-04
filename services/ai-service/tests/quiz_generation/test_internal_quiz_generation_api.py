from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import (
    CreatedQuizQuestionRead,
    QuizGenerationCandidateSetRead,
    QuizGenerationContextRead,
    QuizGenerationPlanQuestionRead,
    QuizGenerationPlanRead,
    QuizGenerationRunResponse,
    RetrievalContextRead,
)


def _run_response() -> QuizGenerationRunResponse:
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


def test_internal_quiz_generation_run_endpoint(client, monkeypatch):
    # Tests internal quiz generation run endpoint returns generated quiz data.
    from app.services.orchestration.langgraph.quiz_generation_graph import QuizGenerationGraphRunner

    monkeypatch.setattr(QuizGenerationGraphRunner, "run", lambda self, payload, config=None: _run_response())

    response = client.post(
        "/internal/quiz-generation/run",
        json={
            "courseUuid": "course-uuid",
            "moduleUuid": "module-uuid",
            "educatorId": 7,
            "additionalInstructions": "Focus on ownership.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["context"]["questionCountPerAttempt"] == 2
    assert len(body["createdQuestions"]) == 2
