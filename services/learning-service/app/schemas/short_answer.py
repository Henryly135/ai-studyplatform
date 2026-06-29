from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ShortAnswerBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ShortAnswerAssessmentUpsertRequest(ShortAnswerBaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    promptText: str = Field(..., min_length=1, max_length=4000)
    rubricText: str = Field(..., min_length=1, max_length=4000)
    maxScore: Decimal = Field(default=Decimal("10.00"), ge=Decimal("1.00"), le=Decimal("100.00"))
    status: Literal["draft", "published", "archived"] = "draft"


class ShortAnswerSubmissionCreateRequest(ShortAnswerBaseModel):
    answerText: str = Field(..., min_length=1, max_length=8000)


class ShortAnswerSubmissionReviewRequest(ShortAnswerBaseModel):
    finalScore: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"))
    finalFeedbackText: str = Field(..., min_length=1, max_length=4000)
    reviewNotes: str | None = Field(default=None, max_length=2000)

    @field_validator("reviewNotes")
    @classmethod
    def blank_notes_to_none(cls, value: str | None) -> str | None:
        return value or None


class ShortAnswerAssessmentResponse(BaseModel):
    assessmentUuid: str
    moduleId: int
    moduleUuid: str
    title: str
    promptText: str
    rubricText: str
    maxScore: Decimal
    status: Literal["draft", "published", "archived"]
    publishedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class ShortAnswerAISuggestionResponse(BaseModel):
    scoreSuggestion: Decimal | None = None
    feedbackText: str | None = None
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


class ShortAnswerSubmissionResponse(BaseModel):
    submissionUuid: str
    assessmentUuid: str
    learnerId: int
    answerText: str
    status: Literal["submitted", "ai_suggested", "reviewed"]
    aiSuggestion: ShortAnswerAISuggestionResponse
    finalScore: Decimal | None = None
    finalFeedbackText: str | None = None
    reviewNotes: str | None = None
    reviewerId: int | None = None
    reviewedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class ShortAnswerLearnerAssessmentResponse(BaseModel):
    assessment: ShortAnswerAssessmentResponse
    latestSubmission: ShortAnswerSubmissionResponse | None = None


class ShortAnswerEvaluationRequest(ShortAnswerBaseModel):
    assessmentUuid: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    promptText: str = Field(..., min_length=1, max_length=4000)
    rubricText: str = Field(..., min_length=1, max_length=4000)
    maxScore: Decimal = Field(..., ge=Decimal("1.00"), le=Decimal("100.00"))
    answerText: str = Field(..., min_length=1, max_length=8000)


class ShortAnswerEvaluationResponse(ShortAnswerBaseModel):
    scoreSuggestion: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"))
    feedbackText: str = Field(..., min_length=1, max_length=4000)
    strengths: list[str] = Field(default_factory=list, max_length=5)
    improvements: list[str] = Field(default_factory=list, max_length=5)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_lists(self) -> "ShortAnswerEvaluationResponse":
        self.strengths = [item.strip() for item in self.strengths if item.strip()]
        self.improvements = [item.strip() for item in self.improvements if item.strip()]
        return self
