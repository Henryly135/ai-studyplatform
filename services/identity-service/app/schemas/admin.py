from pydantic import BaseModel, EmailStr, Field, field_validator


class EducatorInviteTokenRead(BaseModel):
    inviteUuid: str
    createdAt: str
    expiresAt: str
    usedAt: str | None = None
    isUsed: bool


class EducatorInviteTokenListResponse(BaseModel):
    tokens: list[EducatorInviteTokenRead]


class EducatorInviteTokenGenerateResponse(BaseModel):
    inviteUuid: str
    rawToken: str
    expiresAt: str
    inviteUrl: str


class SendEducatorInviteEmailRequest(BaseModel):
    recipientEmail: EmailStr
    inviteUrl: str


class AdminUserRead(BaseModel):
    id: int
    userUuid: str
    email: EmailStr
    userName: str
    identity: str
    roleCodes: list[str]
    emailVerified: bool
    accountStatus: str
    createdAt: str
    updatedAt: str
    lastLoginAt: str | None = None


class AdminUserListResponse(BaseModel):
    users: list[AdminUserRead]


class UpdateUserIdentityRequest(BaseModel):
    identity: str


class UpdateUserStatusRequest(BaseModel):
    accountStatus: str


class EducatorApprovalRead(BaseModel):
    requestUuid: str
    requestStatus: str
    submittedAt: str
    updatedAt: str
    reviewedAt: str | None = None
    reviewComment: str | None = None
    supportingInfo: str | None = None
    supportingFileUrl: str | None = None
    userId: int
    userUuid: str
    email: EmailStr
    userName: str
    identity: str
    accountStatus: str
    emailVerified: bool
    reviewerUserId: int | None = None
    reviewerUserUuid: str | None = None
    reviewerEmail: EmailStr | None = None
    reviewerName: str | None = None


class EducatorApprovalListResponse(BaseModel):
    requests: list[EducatorApprovalRead]


class EducatorApprovalHistoryQuery(BaseModel):
    status: str = Field(default="reviewed")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"reviewed", "approved", "rejected"}:
            raise ValueError("status must be reviewed, approved, or rejected")
        return normalized


class ReviewEducatorApprovalRequest(BaseModel):
    action: str
    reviewComment: str | None = None
