from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ModuleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    content: str = Field(..., min_length=1)
    estimatedMinutes: int | None = Field(default=None, ge=1)
    sortOrder: int | None = Field(default=None, ge=1)


class ModuleUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    content: str | None = None
    estimatedMinutes: int | None = Field(default=None, ge=1)
    sortOrder: int | None = Field(default=None, ge=1)


class ModulePublishRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=20)
    classId: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_class_specific_status(self) -> "ModulePublishRequest":
        normalized_status = self.status.strip().lower()
        if normalized_status == "archived" and not self.classId:
            raise ValueError("classId is required when status is archived")
        if normalized_status != "archived" and self.classId:
            raise ValueError("classId can only be provided when status is archived")
        return self


class ModuleReorderItem(BaseModel):
    moduleUuid: str
    sortOrder: int = Field(..., ge=1)


class ModuleReorderRequest(BaseModel):
    modules: list[ModuleReorderItem] = Field(..., min_length=1)


class ModulePrerequisiteRequest(BaseModel):
    prerequisiteModuleUuid: str


class ModuleProgressUpdateRequest(BaseModel):
    progressStatus: str = Field(..., min_length=1, max_length=20)


class ModuleAuthoringResponse(BaseModel):
    moduleId: int
    moduleUuid: str
    courseId: int
    courseUuid: str
    learningPathId: int
    title: str
    description: str | None
    content: str | None
    sortOrder: int
    estimatedMinutes: int | None
    status: str
    classId: str | None
    prerequisiteModuleUuid: str | None
    createdAt: datetime
    updatedAt: datetime
