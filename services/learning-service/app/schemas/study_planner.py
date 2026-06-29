from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StudyPlannerBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class StudyPlannerMaterialInput(StudyPlannerBaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    materialType: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("materialType", "notes")
    @classmethod
    def blank_optional_strings_to_none(cls, value: str | None) -> str | None:
        return value or None


class StudyPlanCreateRequest(StudyPlannerBaseModel):
    goal: str = Field(..., min_length=5, max_length=500)
    availableMinutesPerWeek: int = Field(..., ge=30, le=10080)
    targetDate: date | None = None
    preferences: str | None = Field(default=None, max_length=1000)
    materials: list[StudyPlannerMaterialInput] = Field(default_factory=list, max_length=20)

    @field_validator("targetDate", mode="before")
    @classmethod
    def blank_target_date_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("preferences")
    @classmethod
    def blank_preferences_to_none(cls, value: str | None) -> str | None:
        return value or None


class StudyPlanPhase(StudyPlannerBaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=160)
    focus: str = Field(..., min_length=1, max_length=500)
    durationDays: int = Field(..., ge=1, le=365)
    outcomes: list[str] = Field(..., min_length=1, max_length=8)


class StudyPlanTopic(StudyPlannerBaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=160)
    reason: str = Field(..., min_length=1, max_length=500)
    materials: list[str] = Field(default_factory=list, max_length=8)


class StudyPlanRevisionItem(StudyPlannerBaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cadence: str = Field(..., min_length=1, max_length=120)
    activity: str = Field(..., min_length=1, max_length=500)


class StudyPlanContent(StudyPlannerBaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    overview: str = Field(..., min_length=1, max_length=1200)
    weeklyCommitmentMinutes: int = Field(..., ge=30, le=10080)
    phases: list[StudyPlanPhase] = Field(..., min_length=1, max_length=8)
    topics: list[StudyPlanTopic] = Field(..., min_length=1, max_length=20)
    revisionSchedule: list[StudyPlanRevisionItem] = Field(..., min_length=1, max_length=12)
    rationale: str = Field(..., min_length=1, max_length=1200)

    @model_validator(mode="after")
    def validate_topic_titles(self) -> "StudyPlanContent":
        titles = [topic.title.strip().lower() for topic in self.topics]
        if len(titles) != len(set(titles)):
            raise ValueError("Topic titles must be unique")
        return self


class StudyPlanUpdateRequest(StudyPlannerBaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "archived"] | None = None
    planContent: StudyPlanContent | None = None
    adjustmentNotes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_has_change(self) -> "StudyPlanUpdateRequest":
        has_value_change = self.title is not None or self.status is not None or self.planContent is not None
        has_notes_change = "adjustmentNotes" in self.model_fields_set
        if not has_value_change and not has_notes_change:
            raise ValueError("At least one field must be provided")
        return self


class StudyPlanGenerationMetadata(BaseModel):
    provider: str | None = None
    model: str | None = None
    usedFallback: bool = False
    fallbackReason: str | None = None


class StudyPlanResponse(BaseModel):
    planUuid: str
    learnerId: int
    title: str
    status: Literal["active", "archived"]
    input: dict[str, Any]
    planContent: StudyPlanContent
    generation: StudyPlanGenerationMetadata
    adjustmentNotes: str | None = None
    createdAt: datetime
    updatedAt: datetime
