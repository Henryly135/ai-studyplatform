from pydantic import BaseModel, Field


class MaterialIndexJobRegisterRequest(BaseModel):
    courseId: int
    moduleId: int
    materialId: int
    educatorId: int | None = Field(default=None, ge=1)
    title: str
    materialType: str
    resourceUrl: str
    storagePath: str
    absolutePath: str | None = None
    contentType: str | None = None
    sizeBytes: int = Field(..., ge=0)
    moduleStatus: str = Field(..., min_length=1, max_length=20)
    storageProvider: str = Field(..., min_length=1, max_length=20)
    storageBucket: str | None = Field(default=None, max_length=255)
    objectKey: str = Field(..., min_length=1, max_length=500)


class MaterialIndexJobRegisterResponse(BaseModel):
    jobId: int
    status: str
    dispatched: bool


class MaterialIndexDeleteRequest(BaseModel):
    materialId: int = Field(..., ge=1)


class MaterialIndexDeleteResponse(BaseModel):
    materialId: int
    deletedSourceCount: int
    deletedChunkCount: int
    deletedJobCount: int


class ReleaseIndexJobsRequest(BaseModel):
    courseId: int
    moduleIds: list[int] = Field(..., min_length=1)


class ReleaseIndexJobsResponse(BaseModel):
    releasedJobIds: list[int]
    releasedCount: int
    dispatchedCount: int


class RetryIndexJobResponse(BaseModel):
    jobId: int
    status: str
    dispatched: bool


class RecoverStaleIndexJobsResponse(BaseModel):
    recoveredJobIds: list[int]
    recoveredCount: int
    dispatchedCount: int


class ReindexAllMaterialsResponse(BaseModel):
    jobIds: list[int]
    queuedCount: int
    skippedCount: int
    dispatchedCount: int
