import re

from pydantic import BaseModel, EmailStr, Field, field_validator

_PASSWORD_RULE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$"
)

def _validate_password(value: str) -> str:
    if not _PASSWORD_RULE.match(value):
        raise ValueError(
            "Password must be at least 8 characters and include uppercase, "
            "lowercase, a number, and a special character."
        )
    return value


class RegisterRequest(BaseModel):
    userName: str = Field(..., max_length=50)
    email: EmailStr
    password: str
    identity: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SwitchRoleRequest(BaseModel):
    identity: str


class UserRead(BaseModel):
    id: int
    userUuid: str
    email: EmailStr
    userName: str
    identity: str
    availableIdentities: list[str] = Field(default_factory=list)
    emailVerified: bool
    accountStatus: str | None = None


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    expiresIn: int
    shouldShowGlobalProfileInitPrompt: bool = False
    user: UserRead


class MeResponse(UserRead):
    id: int
    email: EmailStr
    userName: str
    identity: str
    emailVerified: bool
    accountStatus: str | None = None


class PermissionRead(BaseModel):
    permissionId: int
    permissionCode: str
    permissionName: str
    description: str | None


class PermissionListResponse(BaseModel):
    permissions: list[PermissionRead]
      
class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

    @field_validator("newPassword")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    newPassword: str

    @field_validator("newPassword")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class EducatorInviteRegisterRequest(BaseModel):
    userName: str = Field(..., max_length=50)
    email: EmailStr
    password: str
    inviteToken: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)
