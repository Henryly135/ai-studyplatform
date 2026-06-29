from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class QuizQuestionOptionWriteRequest(BaseModel):
    optionUuid: str | None = None
    optionLabel: str | None = Field(default=None, max_length=10)
    optionText: str = Field(..., min_length=1)
    sortOrder: int = Field(..., ge=1)
    isCorrect: bool = False


class QuizQuestionWriteRequest(BaseModel):
    questionUuid: str | None = None
    questionText: str = Field(..., min_length=1)
    explanationText: str | None = None
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
