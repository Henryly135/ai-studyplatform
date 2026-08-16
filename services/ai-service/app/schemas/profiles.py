from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GlobalProfileInitRequest(BaseModel):
    supportRole: str = Field(..., min_length=1, max_length=200)
    helpStyle: str = Field(..., min_length=1, max_length=200)
    learningFocus: str = Field(..., min_length=1, max_length=200)
    responseTone: str = Field(..., min_length=1, max_length=200)


class GlobalProfileUpdateRequest(GlobalProfileInitRequest):
    """Learner preferences used to regenerate the active global profile."""


class GlobalProfileRead(BaseModel):
    learnerId: int
    profileType: str = "global_skill"
    version: int | None = None
    objectKey: str | None = None
    content: str
    preferences: dict[str, str] = Field(default_factory=dict)
    isDefaultProfile: bool = False
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class GlobalProfileExistenceRead(BaseModel):
    learnerId: int
    exists: bool


class ModuleProfileRead(BaseModel):
    learnerId: int
    courseUuid: str
    moduleUuid: str
    profileType: str = "module_profile"
    version: int | None = None
    objectKey: str | None = None
    content: dict[str, Any]
    isDefaultProfile: bool = False
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class ModuleProfileInitBatchRequest(BaseModel):
    learnerId: int
    courseUuid: str = Field(..., min_length=1)
    moduleUuids: list[str] = Field(default_factory=list)
    triggerSource: str = Field(..., min_length=1, max_length=100)


class ModuleProfileInitBatchFailedItem(BaseModel):
    moduleUuid: str
    code: str = "MODULE_PROFILE_INIT_FAILED"
    message: str


class ModuleProfileInitBatchResponse(BaseModel):
    learnerId: int
    courseUuid: str
    triggerSource: str
    requestedCount: int
    initializedCount: int
    skippedCount: int
    failedCount: int
    failedItems: list[ModuleProfileInitBatchFailedItem] = Field(default_factory=list)
