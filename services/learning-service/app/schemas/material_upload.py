from datetime import datetime

from pydantic import BaseModel, Field


class MultipartMaterialUploadInitRequest(BaseModel):
    fileName: str = Field(..., min_length=1, max_length=255)
    contentType: str | None = Field(default=None, max_length=255)
    sizeBytes: int = Field(..., gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    materialType: str | None = Field(default=None, min_length=1, max_length=20)
    sortOrder: int | None = Field(default=None, ge=1)


class MultipartMaterialUploadInitResponse(BaseModel):
    uploadSessionUuid: str
    uploadId: str
    bucket: str | None
    objectKey: str
    storageProvider: str
    partUrlExpiresSeconds: int


class MultipartMaterialUploadPartUrlResponse(BaseModel):
    uploadSessionUuid: str
    partNumber: int
    method: str
    uploadUrl: str
    expiresSeconds: int


class MultipartMaterialUploadCompletedPart(BaseModel):
    partNumber: int = Field(..., ge=1, le=10000)
    etag: str = Field(..., min_length=1, max_length=255)


class MultipartMaterialUploadCompleteRequest(BaseModel):
    parts: list[MultipartMaterialUploadCompletedPart] = Field(..., min_length=1)


class MultipartMaterialUploadSessionResponse(BaseModel):
    uploadSessionId: int
    uploadSessionUuid: str
    moduleId: int
    title: str
    materialType: str
    sortOrder: int
    originalFilename: str
    contentType: str | None
    sizeBytes: int | None
    storageProvider: str
    bucket: str | None
    objectKey: str
    status: str
    materialId: int | None
    createdAt: datetime
    updatedAt: datetime
