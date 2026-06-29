from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShortAnswerBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


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
    def normalize_score_and_lists(self) -> "ShortAnswerEvaluationResponse":
        self.scoreSuggestion = Decimal(self.scoreSuggestion).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.strengths = [item.strip() for item in self.strengths if item.strip()]
        self.improvements = [item.strip() for item in self.improvements if item.strip()]
        return self
