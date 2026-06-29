from __future__ import annotations

from app.services.workflows.quiz_generation.schemas import (
    EducatorQuizDraftGenerationRequest,
    QuizGenerationCandidateSetRead,
    QuizGenerationPlanQuestionRead,
    QuizGenerationPlanRead,
    RetrievalContextRead,
)
from app.services.workflows.quiz_generation.services.educator_draft_service import EducatorQuizDraftGenerationService


def _payload() -> EducatorQuizDraftGenerationRequest:
    return EducatorQuizDraftGenerationRequest(
        courseUuid="course-uuid",
        moduleUuid="module-uuid",
        educatorId=7,
        courseTitle="Algorithms",
        moduleTitle="Graphs",
        quizTitle="Graph Quiz",
        questionCount=2,
        availableQuestionCount=0,
        difficulty="mixed",
        questionTypes=["multiple_choice"],
        learningObjectives=["Explain BFS", "Apply DFS"],
        materialScope="Module materials",
        additionalInstructions="Include one applied scenario.",
    )


def _plan() -> QuizGenerationPlanRead:
    return QuizGenerationPlanRead(
        titleSuggestion="Graph Quiz",
        overview="Cover traversal basics.",
        plannedQuestionCount=2,
        questions=[
            QuizGenerationPlanQuestionRead(
                sortOrder=1,
                learningObjective="Explain BFS",
                difficulty="easy",
                questionStyle="multiple_choice",
                rationale="Core traversal concept.",
            ),
            QuizGenerationPlanQuestionRead(
                sortOrder=2,
                learningObjective="Apply DFS",
                difficulty="medium",
                questionStyle="multiple_choice",
                rationale="Common application concept.",
            ),
        ],
    )


def _candidate_set() -> QuizGenerationCandidateSetRead:
    return QuizGenerationCandidateSetRead(
        questionCount=2,
        questions=[
            {
                "questionText": "What does BFS use?",
                "explanationText": "BFS uses a queue.",
                "sourceGrounding": "Graphs module notes, BFS section.",
                "sortOrder": 1,
                "isActive": True,
                "options": [
                    {"optionLabel": "A", "optionText": "Queue", "sortOrder": 1, "isCorrect": True},
                    {"optionLabel": "B", "optionText": "Stack", "sortOrder": 2, "isCorrect": False},
                ],
            },
            {
                "questionText": "What can DFS use?",
                "explanationText": "DFS can use recursion.",
                "sourceGrounding": "Graphs module notes, DFS section.",
                "sortOrder": 2,
                "isActive": True,
                "options": [
                    {"optionLabel": "A", "optionText": "Recursion", "sortOrder": 1, "isCorrect": True},
                    {"optionLabel": "B", "optionText": "A FIFO queue only", "sortOrder": 2, "isCorrect": False},
                ],
            },
        ],
    )


def test_educator_quiz_draft_generation_reuses_quiz_generation_services(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_load_context(self, **kwargs):
        calls["retrieval"] = kwargs
        return RetrievalContextRead(usedRetrieval=False, queryText="query", topK=5, chunkCount=0, chunks=[])

    def fake_build_plan(self, **kwargs):
        calls["planning"] = kwargs
        return _plan()

    def fake_generate_candidates(self, **kwargs):
        calls["generation"] = kwargs
        return _candidate_set()

    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.educator_draft_service.decode_course_uuid",
        lambda _: 11,
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.educator_draft_service.decode_module_uuid",
        lambda _: 22,
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.educator_draft_service.QuizGenerationRetrievalService.load_context",
        fake_load_context,
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.educator_draft_service.QuizGenerationPlanningService.build_plan",
        fake_build_plan,
    )
    monkeypatch.setattr(
        "app.services.workflows.quiz_generation.services.educator_draft_service.QuizCandidateGenerationService.generate_candidates",
        fake_generate_candidates,
    )

    response = EducatorQuizDraftGenerationService(session=object()).generate_draft(_payload())

    assert response.context.quizStatus == "draft"
    assert response.context.questionCountPerAttempt == 2
    assert response.candidateSet.questionCount == 2
    assert response.candidateSet.questions[0].sourceGrounding == "Graphs module notes, BFS section."
    assert "Include one applied scenario" in calls["retrieval"]["additional_instructions"]
    assert calls["planning"]["profile_context"] is None
