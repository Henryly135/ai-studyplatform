from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.quiz import QuizQuestionWriteRequest


class QuizGenerationContextRequest(BaseModel):
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)


class QuizGenerationLearnerAccessRequest(BaseModel):
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    learnerId: int = Field(..., ge=1)


class QuizGenerationLearnerAccessResponse(BaseModel):
    allowed: bool


class QuizGenerationContextResponse(BaseModel):
    courseId: int
    moduleId: int
    courseUuid: str
    moduleUuid: str
    courseTitle: str
    moduleTitle: str
    quizId: int
    quizUuid: str
    quizTitle: str
    quizDescription: str | None = None
    quizStatus: str
    questionCountPerAttempt: int
    timeLimitSeconds: int | None = None
    shuffleQuestions: bool
    shuffleOptions: bool
    availableQuestionCount: int


class GeneratedQuizQuestionsCreateRequest(BaseModel):
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    questions: list[QuizQuestionWriteRequest] = Field(..., min_length=1)


class GeneratedQuizQuestionRefResponse(BaseModel):
    questionId: int
    questionUuid: str
    sortOrder: int


class GeneratedQuizQuestionsCreateResponse(BaseModel):
    quizId: int
    quizUuid: str
    createdQuestions: list[GeneratedQuizQuestionRefResponse]


class GeneratedQuizAttemptStartRequest(BaseModel):
    questionUuids: list[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_unique_question_uuids(self) -> "GeneratedQuizAttemptStartRequest":
        if len(self.questionUuids) != len(set(self.questionUuids)):
            raise ValueError("questionUuids must be unique")
        return self


class GeneratedQuizAttemptInternalStartRequest(BaseModel):
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    learnerId: int = Field(..., ge=1)
    questionUuids: list[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_unique_question_uuids(self) -> "GeneratedQuizAttemptInternalStartRequest":
        if len(self.questionUuids) != len(set(self.questionUuids)):
            raise ValueError("questionUuids must be unique")
        return self
