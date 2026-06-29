from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ContentDraftType = Literal[
    "summary",
    "learning_objectives",
    "activity_suggestions",
    "differentiated_explanation",
    "slide_outline",
]


class ContentDraftBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ContentDraftGenerateRequest(ContentDraftBaseModel):
    contentType: ContentDraftType
    title: str | None = Field(default=None, max_length=200)
    teacherPrompt: str | None = Field(default=None, max_length=4000)
    materialScope: str | None = Field(default=None, max_length=1000)


class ContentDraftGroundingItem(ContentDraftBaseModel):
    sourceTitle: str = Field(..., min_length=1, max_length=200)
    sourceType: str = Field(..., min_length=1, max_length=50)
    reference: str = Field(..., min_length=1, max_length=500)
    rationale: str = Field(..., min_length=1, max_length=500)


class ContentDraftAIResponse(ContentDraftBaseModel):
    contentType: ContentDraftType
    title: str = Field(..., min_length=1, max_length=200)
    structuredContent: dict[str, Any] = Field(..., min_length=1)
    grounding: list[ContentDraftGroundingItem] = Field(..., min_length=1)
    confidenceScore: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("1.00"))
    isFallback: bool = False
    fallbackReason: str | None = Field(default=None, max_length=500)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=160)


class ContentDraftUpdateRequest(ContentDraftBaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    structuredContent: dict[str, Any] | None = Field(default=None, min_length=1)
    grounding: list[ContentDraftGroundingItem] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_has_update(self) -> "ContentDraftUpdateRequest":
        if self.title is None and self.structuredContent is None and self.grounding is None:
            raise ValueError("At least one field is required")
        return self


class ContentDraftResponse(BaseModel):
    draftUuid: str
    moduleId: int
    moduleUuid: str
    contentType: ContentDraftType
    title: str
    teacherPrompt: str | None = None
    materialScope: str | None = None
    structuredContent: dict[str, Any]
    grounding: list[ContentDraftGroundingItem]
    confidenceScore: Decimal
    isFallback: bool
    fallbackReason: str | None = None
    provider: str | None = None
    model: str | None = None
    createdBy: int | None = None
    updatedBy: int | None = None
    createdAt: datetime
    updatedAt: datetime
