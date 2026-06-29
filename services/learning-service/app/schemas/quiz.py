from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuizQuestionOptionWriteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    optionUuid: str | None = None
    optionLabel: str | None = Field(default=None, max_length=10)
    optionText: str = Field(..., min_length=1)
    sortOrder: int = Field(..., ge=1)
    isCorrect: bool = False


class QuizQuestionWriteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    questionUuid: str | None = None
    questionText: str = Field(..., min_length=1)
    explanationText: str | None = None
    sourceGrounding: str | None = Field(default=None, max_length=1000)
    sortOrder: int = Field(..., ge=1)
    isActive: bool = True
    options: list[QuizQuestionOptionWriteRequest] = Field(..., min_length=2)

    @model_validator(mode="after")
    def validate_single_correct_option(self) -> "QuizQuestionWriteRequest":
        correct_count = sum(1 for option in self.options if option.isCorrect)
        if correct_count != 1:
            raise ValueError("Each question must have exactly one correct option")
        option_sort_orders = [option.sortOrder for option in self.options]
        if len(option_sort_orders) != len(set(option_sort_orders)):
            raise ValueError("Option sortOrder values must be unique within each question")
        return self


class QuizUpsertRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    timeLimitSeconds: int | None = Field(default=None, ge=1)
    questionCountPerAttempt: int = Field(..., ge=1)
    shuffleQuestions: bool = True
    shuffleOptions: bool = False
    questions: list[QuizQuestionWriteRequest] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_question_sort_orders(self) -> "QuizUpsertRequest":
        question_sort_orders = [question.sortOrder for question in self.questions]
        if len(question_sort_orders) != len(set(question_sort_orders)):
            raise ValueError("Question sortOrder values must be unique")
        question_uuids = [question.questionUuid for question in self.questions if question.questionUuid]
        if len(question_uuids) != len(set(question_uuids)):
            raise ValueError("Question questionUuid values must be unique within the request")
        return self


class QuizPublishRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=20)


class EducatorQuizDraftGenerateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=200)
    questionCount: int = Field(default=5, ge=1, le=20)
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "mixed"
    questionTypes: list[Literal["multiple_choice", "true_false"]] = Field(
        default_factory=lambda: ["multiple_choice"],
        min_length=1,
        max_length=2,
    )
    learningObjectives: list[str] = Field(default_factory=list, max_length=10)
    materialScope: str | None = Field(default=None, max_length=1000)
    additionalInstructions: str | None = Field(default=None, max_length=2000)
    replaceExistingQuestions: bool = True
    timeLimitSeconds: int | None = Field(default=None, ge=1)
    shuffleQuestions: bool = True
    shuffleOptions: bool = False

    @model_validator(mode="after")
    def validate_draft_generation_request(self) -> "EducatorQuizDraftGenerateRequest":
        if len(self.questionTypes) != len(set(self.questionTypes)):
            raise ValueError("questionTypes must be unique")
        normalized_objectives = [objective.strip() for objective in self.learningObjectives if objective.strip()]
        if len(normalized_objectives) != len(self.learningObjectives):
            raise ValueError("learningObjectives cannot contain blank values")
        self.learningObjectives = normalized_objectives
        return self


class EducatorQuizDraftCandidateOption(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    optionLabel: str | None = Field(default=None, max_length=10)
    optionText: str = Field(..., min_length=1, max_length=500)
    sortOrder: int = Field(..., ge=1)
    isCorrect: bool = False


class EducatorQuizDraftCandidateQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    questionText: str = Field(..., min_length=1, max_length=2000)
    explanationText: str | None = Field(default=None, max_length=2000)
    sourceGrounding: str = Field(..., min_length=1, max_length=1000)
    sortOrder: int = Field(..., ge=1)
    isActive: bool = True
    options: list[EducatorQuizDraftCandidateOption] = Field(..., min_length=2)

    @model_validator(mode="after")
    def validate_options(self) -> "EducatorQuizDraftCandidateQuestion":
        option_sort_orders = [option.sortOrder for option in self.options]
        if len(option_sort_orders) != len(set(option_sort_orders)):
            raise ValueError("Option sortOrder values must be unique within each question")
        if sum(1 for option in self.options if option.isCorrect) != 1:
            raise ValueError("Each generated question must have exactly one correct option")
        return self


class EducatorQuizDraftCandidateSet(BaseModel):
    questionCount: int = Field(..., ge=1, le=20)
    questions: list[EducatorQuizDraftCandidateQuestion] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_question_count(self) -> "EducatorQuizDraftCandidateSet":
        if len(self.questions) != self.questionCount:
            raise ValueError("questionCount must match the number of generated questions")
        question_sort_orders = [question.sortOrder for question in self.questions]
        if len(question_sort_orders) != len(set(question_sort_orders)):
            raise ValueError("Question sortOrder values must be unique")
        return self


class EducatorQuizDraftPreviewResponse(BaseModel):
    title: str
    questionCount: int = Field(..., ge=1, le=20)
    difficulty: Literal["easy", "medium", "hard", "mixed"]
    questionTypes: list[Literal["multiple_choice", "true_false"]]
    replaceExistingQuestions: bool
    timeLimitSeconds: int | None = Field(default=None, ge=1)
    shuffleQuestions: bool
    shuffleOptions: bool
    retrievalUsed: bool
    sourceChunkCount: int = Field(..., ge=0)
    candidateSet: EducatorQuizDraftCandidateSet


class EducatorQuizDraftAcceptRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=200)
    replaceExistingQuestions: bool = True
    timeLimitSeconds: int | None = Field(default=None, ge=1)
    shuffleQuestions: bool = True
    shuffleOptions: bool = False
    candidateSet: dict[str, Any]


class QuizOptionResponse(BaseModel):
    optionId: int
    optionUuid: str
    optionLabel: str | None
    optionText: str
    sortOrder: int
    isCorrect: bool | None = None


class QuizQuestionResponse(BaseModel):
    questionId: int
    questionUuid: str
    questionText: str
    explanationText: str | None
    sourceGrounding: str | None = None
    sortOrder: int
    isActive: bool | None = None
    options: list[QuizOptionResponse]


class QuizAuthoringResponse(BaseModel):
    quizId: int
    quizUuid: str
    moduleId: int
    moduleUuid: str
    title: str
    description: str | None
    status: str
    timeLimitSeconds: int | None
    questionCountPerAttempt: int
    availableQuestionCount: int
    shuffleQuestions: bool
    shuffleOptions: bool
    passingRule: str
    publishedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime
    questions: list[QuizQuestionResponse]


class QuizQuestionPageResponse(BaseModel):
    items: list[QuizQuestionResponse]
    page: int
    pageSize: int
    total: int
    totalPages: int


class QuizAttemptStartQuestionResponse(BaseModel):
    questionId: int
    questionUuid: str
    questionText: str
    explanationText: str | None
    questionOrder: int
    options: list[QuizOptionResponse]


class QuizAttemptStartResponse(BaseModel):
    quizId: int
    quizUuid: str
    moduleId: int
    moduleUuid: str
    attemptSessionToken: str
    attemptNumber: int
    questionCount: int
    timeLimitSeconds: int | None
    startedAt: datetime
    expiresAt: datetime | None
    questions: list[QuizAttemptStartQuestionResponse]


class QuizAttemptAnswerSubmitRequest(BaseModel):
    questionUuid: str
    selectedOptionUuid: str | None = None


class QuizAttemptSubmitRequest(BaseModel):
    answers: list[QuizAttemptAnswerSubmitRequest] = Field(..., min_length=1)
    timedOut: bool = False


class QuizAttemptAnswerResultResponse(BaseModel):
    questionId: int
    questionUuid: str
    questionOrder: int
    questionText: str
    explanationText: str | None
    selectedOptionId: int | None
    selectedOptionUuid: str | None
    selectedOptionText: str | None
    correctOptionId: int
    correctOptionUuid: str
    correctOptionText: str
    isCorrect: bool
    optionOrderSnapshot: list[int]
    optionTextsSnapshot: list[dict[str, Any]]


class QuizAttemptResultResponse(BaseModel):
    quizAttemptId: int
    quizAttemptUuid: str
    quizId: int
    quizUuid: str
    moduleId: int
    moduleUuid: str
    learnerId: int
    attemptNumber: int
    questionCount: int
    correctCount: int
    scorePercent: str
    isPassed: bool
    isTimedOut: bool
    moduleCompleted: bool
    timeLimitSeconds: int | None
    startedAt: datetime
    submittedAt: datetime
    durationSeconds: int | None
    answers: list[QuizAttemptAnswerResultResponse]


class QuizAttemptSummaryResponse(BaseModel):
    quizAttemptId: int
    quizAttemptUuid: str
    attemptNumber: int
    questionCount: int
    correctCount: int
    scorePercent: str
    isPassed: bool
    isTimedOut: bool
    startedAt: datetime
    submittedAt: datetime
    durationSeconds: int | None


class QuizAttemptHistoryResponse(BaseModel):
    quizId: int
    quizUuid: str
    moduleId: int
    moduleUuid: str
    title: str
    timeLimitSeconds: int | None
    passedOnce: bool
    attempts: list[QuizAttemptSummaryResponse]
