from typing import Any

from pydantic import BaseModel, Field
from datetime import datetime


class SmokeTaskRequest(BaseModel):
    message: str = Field(default="pong", min_length=1, max_length=200)


class SmokeTaskEnqueueResponse(BaseModel):
    success: bool = True
    task_id: str
    queue: str
    requested_by: int
    status: str


class SmokeTaskResultResponse(BaseModel):
    success: bool = True
    task_id: str
    status: str
    result: dict[str, Any] | None = None


class IndexJobStatusResponse(BaseModel):
    success: bool = True
    job_id: int
    job_type: str
    source_type: str
    source_ref_id: str
    course_id: int | None = None
    module_id: int | None = None
    material_id: int | None = None
    status: str
    priority: int
    attempt_count: int
    error_message: str | None = None
    worker_id: str | None = None
    next_retry_at: datetime | None = None
    locked_at: datetime | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
