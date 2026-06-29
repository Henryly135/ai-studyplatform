from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ContentDraftType = Literal[
    "summary",
    "learning_objectives",
    "activity_suggestions",
    "differentiated_explanation",
    "slide_outline",
]


class ContentGenerationBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ContentGenerationMaterialInput(ContentGenerationBaseModel):
    materialId: int | None = Field(default=None, ge=1)
    title: str = Field(..., min_length=1, max_length=200)
    materialType: str = Field(..., min_length=1, max_length=50)
    resourceUrl: str | None = Field(default=None, max_length=1000)
    summary: str | None = Field(default=None, max_length=2000)


class ContentGenerationRequest(ContentGenerationBaseModel):
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str = Field(..., min_length=1)
    educatorId: int = Field(..., ge=1)
    courseTitle: str = Field(..., min_length=1, max_length=200)
    moduleTitle: str = Field(..., min_length=1, max_length=200)
    moduleDescription: str | None = Field(default=None, max_length=2000)
    moduleContent: str | None = Field(default=None, max_length=8000)
    contentType: ContentDraftType
    materialScope: str | None = Field(default=None, max_length=1000)
    teacherPrompt: str | None = Field(default=None, max_length=4000)
    materials: list[ContentGenerationMaterialInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_generation_context(self) -> "ContentGenerationRequest":
        has_teacher_prompt = bool(self.teacherPrompt)
        has_module_content = bool(self.moduleContent)
        has_materials = bool(self.materials)
        if not (has_teacher_prompt or has_module_content or has_materials):
            raise ValueError("teacherPrompt, moduleContent, or materials are required")
        return self


class ContentGenerationGroundingItem(ContentGenerationBaseModel):
    sourceTitle: str = Field(..., min_length=1, max_length=200)
    sourceType: str = Field(..., min_length=1, max_length=50)
    reference: str = Field(..., min_length=1, max_length=500)
    rationale: str = Field(..., min_length=1, max_length=500)


class ContentGenerationResponse(ContentGenerationBaseModel):
    contentType: ContentDraftType
    title: str = Field(..., min_length=1, max_length=200)
    structuredContent: dict[str, Any] = Field(..., min_length=1)
    grounding: list[ContentGenerationGroundingItem] = Field(..., min_length=1)
    confidenceScore: float = Field(..., ge=0, le=1)
    isFallback: bool = False
    fallbackReason: str | None = Field(default=None, max_length=500)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=160)
