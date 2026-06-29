from pydantic import BaseModel, EmailStr, Field


class UserDirectoryRead(BaseModel):
    id: int
    userUuid: str
    email: EmailStr
    userName: str
    identity: str
    roleCodes: list[str]
    emailVerified: bool
    accountStatus: str


class UserDirectoryLookupRequest(BaseModel):
    userIds: list[int] = Field(..., min_length=1)


class UserDirectoryLookupResponse(BaseModel):
    users: list[UserDirectoryRead]
