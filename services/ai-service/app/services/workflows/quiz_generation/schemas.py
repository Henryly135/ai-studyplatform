from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.profiles import GlobalProfileRead, ModuleProfileRead


class QuizGenerationRequest(BaseModel):
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    educatorId: int = Field(..., ge=1)
    learnerId: int | None = Field(default=None, ge=1)
    additionalInstructions: str | None = Field(default=None, max_length=2000)


class QuizGenerationAutoStartRequest(BaseModel):
    additionalInstructions: str | None = Field(default=None, max_length=2000)


class QuizGenerationAutoStartRunRequest(BaseModel):
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    actorId: int = Field(..., ge=1)
    additionalInstructions: str | None = Field(default=None, max_length=2000)


class EducatorQuizDraftGenerationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    educatorId: int = Field(..., ge=1)
    courseTitle: str = Field(..., min_length=1, max_length=200)
    moduleTitle: str = Field(..., min_length=1, max_length=200)
    quizTitle: str = Field(..., min_length=1, max_length=200)
    questionCount: int = Field(..., ge=1, le=20)
    availableQuestionCount: int = Field(default=0, ge=0)
    timeLimitSeconds: int | None = Field(default=None, ge=1)
    shuffleQuestions: bool = True
    shuffleOptions: bool = False
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "mixed"
    questionTypes: list[Literal["multiple_choice", "true_false"]] = Field(
        default_factory=lambda: ["multiple_choice"],
        min_length=1,
        max_length=2,
    )
    learningObjectives: list[str] = Field(default_factory=list, max_length=10)
    materialScope: str | None = Field(default=None, max_length=1000)
    additionalInstructions: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_unique_question_types(self) -> "EducatorQuizDraftGenerationRequest":
        if len(self.questionTypes) != len(set(self.questionTypes)):
            raise ValueError("questionTypes must be unique")
        normalized_objectives = [objective.strip() for objective in self.learningObjectives if objective.strip()]
        if len(normalized_objectives) != len(self.learningObjectives):
            raise ValueError("learningObjectives cannot contain blank values")
        self.learningObjectives = normalized_objectives
        return self


class QuizGenerationRunStartResponse(BaseModel):
    runId: str
    status: Literal["queued", "running", "completed", "failed"]


class QuizGenerationRunStatusResponse(BaseModel):
    runId: str
    courseUuid: str
    moduleUuid: str
    actorId: int = Field(..., ge=1)
    status: Literal["queued", "running", "completed", "failed"]
    currentStep: str | None = None
    message: str | None = None
    startedAt: datetime
    updatedAt: datetime
    error: str | None = None
    attemptStartResponse: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)


class QuizGenerationContextRead(BaseModel):
    courseId: int = Field(..., ge=1)
    moduleId: int = Field(..., ge=1)
    courseUuid: str
    moduleUuid: str
    courseTitle: str
    moduleTitle: str
    quizId: int = Field(..., ge=1)
    quizUuid: str
    quizTitle: str
    quizDescription: str | None = None
    quizStatus: str
    questionCountPerAttempt: int = Field(..., ge=1)
    timeLimitSeconds: int | None = Field(default=None, ge=1)
    shuffleQuestions: bool
    shuffleOptions: bool
    availableQuestionCount: int = Field(..., ge=0)


class QuizGenerationProfileContextRead(BaseModel):
    learnerId: int = Field(..., ge=1)
    globalProfile: GlobalProfileRead
    moduleProfile: ModuleProfileRead


class RetrievalContextChunkRead(BaseModel):
    chunkId: int = Field(..., ge=1)
    materialId: int | None = Field(default=None, ge=1)
    moduleId: int | None = Field(default=None, ge=1)
    headingPath: str | None = None
    score: float
    content: str


class RetrievalContextRead(BaseModel):
    usedRetrieval: bool
    queryText: str
    topK: int = Field(..., ge=1)
    chunkCount: int = Field(..., ge=0)
    chunks: list[RetrievalContextChunkRead]


class QuizGenerationPlanQuestionRead(BaseModel):
    sortOrder: int = Field(..., ge=1)
    learningObjective: str = Field(..., min_length=1, max_length=500)
    difficulty: Literal["easy", "medium", "hard"]
    questionStyle: Literal["multiple_choice", "true_false"]
    rationale: str = Field(..., min_length=1, max_length=500)


class QuizGenerationPlanRead(BaseModel):
    titleSuggestion: str | None = Field(default=None, max_length=200)
    overview: str = Field(..., min_length=1, max_length=1000)
    plannedQuestionCount: int = Field(..., ge=1)
    questions: list[QuizGenerationPlanQuestionRead]

    @model_validator(mode="after")
    def validate_question_count(self) -> "QuizGenerationPlanRead":
        if len(self.questions) != self.plannedQuestionCount:
            raise ValueError("plannedQuestionCount must match the number of planned questions")
        return self


class QuizGenerationCandidateOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optionLabel: str | None = Field(default=None, max_length=10)
    optionText: str = Field(..., min_length=1, max_length=500)
    sortOrder: int = Field(..., ge=1)
    isCorrect: bool = False


class QuizGenerationCandidateQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questionText: str = Field(..., min_length=1, max_length=2000)
    explanationText: str | None = Field(default=None, max_length=2000)
    sourceGrounding: str = Field(..., min_length=1, max_length=1000)
    sortOrder: int = Field(..., ge=1)
    isActive: bool = True
    options: list[QuizGenerationCandidateOption] = Field(..., min_length=2)

    @model_validator(mode="after")
    def validate_options(self) -> "QuizGenerationCandidateQuestion":
        option_sort_orders = [option.sortOrder for option in self.options]
        if len(option_sort_orders) != len(set(option_sort_orders)):
            raise ValueError("Option sortOrder values must be unique within each question")
        if sum(1 for option in self.options if option.isCorrect) != 1:
            raise ValueError("Each generated question must have exactly one correct option")
        return self


class QuizGenerationCandidateSetRead(BaseModel):
    questionCount: int = Field(..., ge=1)
    questions: list[QuizGenerationCandidateQuestion]

    @model_validator(mode="after")
    def validate_question_count(self) -> "QuizGenerationCandidateSetRead":
        if len(self.questions) != self.questionCount:
            raise ValueError("questionCount must match the number of generated questions")
        question_sort_orders = [question.sortOrder for question in self.questions]
        if len(question_sort_orders) != len(set(question_sort_orders)):
            raise ValueError("Question sortOrder values must be unique")
        return self


class CreatedQuizQuestionRead(BaseModel):
    questionId: int = Field(..., ge=1)
    questionUuid: str
    sortOrder: int = Field(..., ge=1)


class QuizAttemptStartOptionRead(BaseModel):
    optionId: int = Field(..., ge=1)
    optionUuid: str
    optionLabel: str | None = None
    optionText: str
    sortOrder: int = Field(..., ge=1)


class QuizAttemptStartQuestionRead(BaseModel):
    questionId: int = Field(..., ge=1)
    questionUuid: str
    questionText: str
    explanationText: str | None = None
    questionOrder: int = Field(..., ge=1)
    options: list[QuizAttemptStartOptionRead]


class QuizGeneratedAttemptStartResponse(BaseModel):
    quizId: int = Field(..., ge=1)
    quizUuid: str
    moduleId: int = Field(..., ge=1)
    moduleUuid: str
    attemptSessionToken: str
    attemptNumber: int = Field(..., ge=1)
    questionCount: int = Field(..., ge=1)
    timeLimitSeconds: int | None = Field(default=None, ge=1)
    startedAt: datetime
    expiresAt: datetime | None = None
    questions: list[QuizAttemptStartQuestionRead]


class QuizGenerationRunResponse(BaseModel):
    context: QuizGenerationContextRead
    profileContext: QuizGenerationProfileContextRead | None = None
    retrievalContext: RetrievalContextRead
    plan: QuizGenerationPlanRead
    candidateSet: QuizGenerationCandidateSetRead
    createdQuestions: list[CreatedQuizQuestionRead]


class EducatorQuizDraftGenerationResponse(BaseModel):
    context: QuizGenerationContextRead
    retrievalContext: RetrievalContextRead
    plan: QuizGenerationPlanRead
    candidateSet: QuizGenerationCandidateSetRead


class QuizGenerationWorkflowState(TypedDict, total=False):
    request: QuizGenerationRequest
    context: QuizGenerationContextRead
    profileContext: QuizGenerationProfileContextRead
    retrievalContext: RetrievalContextRead
    plan: QuizGenerationPlanRead
    candidateSet: QuizGenerationCandidateSetRead
    createdQuestions: list[CreatedQuizQuestionRead]


class QuizGenerationAutoStartWorkflowState(TypedDict, total=False):
    request: QuizGenerationAutoStartRunRequest
    generationRequest: QuizGenerationRequest
    generationResult: QuizGenerationRunResponse
    attemptStartResponse: QuizGeneratedAttemptStartResponse
