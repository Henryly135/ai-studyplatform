from __future__ import annotations

from pydantic import BaseModel, Field


class AIChatContextAccessRequest(BaseModel):
    courseUuid: str = Field(..., min_length=1)
    moduleUuid: str | None = Field(default=None, min_length=1)
    userId: int = Field(..., ge=1)
    identity: str = Field(..., min_length=1)


class AIChatContextAccessResponse(BaseModel):
    allowed: bool
