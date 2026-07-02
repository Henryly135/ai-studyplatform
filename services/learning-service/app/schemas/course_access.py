from __future__ import annotations

from pydantic import BaseModel, Field


class ForumCourseAccessRequest(BaseModel):
    courseUuid: str = Field(..., min_length=1)
    userId: int = Field(..., ge=1)
    identity: str = Field(..., min_length=1)


class ForumCourseAccessResponse(BaseModel):
    allowed: bool
