from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_access_token, require_auth
from app.core.public_url import resolve_public_frontend_base_url
from app.db.session import get_db_session
from app.schemas.auth import ChangePasswordRequest, EducatorInviteRegisterRequest, ForgotPasswordRequest, LoginRequest, MeResponse, RegisterRequest, ResetPasswordRequest, TokenResponse, PermissionListResponse
from app.services.auth_service import AuthService
from app.services.auth_service import AuthServiceError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, request: Request, session: Session = Depends(get_db_session)):
    return AuthService(session).register(
        usr_name=req.userName,
        email=str(req.email),
        password=req.password,
        identity=req.identity,
        public_frontend_base_url=resolve_public_frontend_base_url(request),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    request: Request,
    session: Session = Depends(get_db_session),
):
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else None
    if not ip_address and request.client:
        ip_address = request.client.host

    try:
        return AuthService(session).login(
            email=str(req.email),
            password=req.password,
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/verify-email")
def verify_email(token: str | None = None, session: Session = Depends(get_db_session)):
    return AuthService(session).verify_email(token=token)


@router.post("/resend-verification")
def resend_verification(payload: dict, request: Request, session: Session = Depends(get_db_session)):
    return AuthService(session).resend_verification(
        email=payload.get("email"),
        public_frontend_base_url=resolve_public_frontend_base_url(request),
    )


@router.get("/me", response_model=MeResponse)
def me(current_user: dict = Depends(require_auth)):
    return current_user


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, request: Request, session: Session = Depends(get_db_session)):
    return AuthService(session).forgot_password(
        email=str(req.email),
        public_frontend_base_url=resolve_public_frontend_base_url(request),
    )


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, session: Session = Depends(get_db_session)):
    return AuthService(session).reset_password(token=req.token, new_password=req.newPassword)


@router.get("/me/permissions", response_model=PermissionListResponse)
def me_permissions(
    _: dict = Depends(require_auth),
    token: str = Depends(require_access_token),
    session: Session = Depends(get_db_session),
):
    try:
        return AuthService(session).get_current_user_permissions(token)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
  
@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(require_auth),
    session: Session = Depends(get_db_session),
):
    return AuthService(session).change_password(
        user_id=current_user["id"],
        current_password=req.currentPassword,
        new_password=req.newPassword,
    )


@router.get("/invite/educator/validate")
def validate_educator_invite(token: str | None = None, session: Session = Depends(get_db_session)):
    """Public endpoint to validate an educator invite token before showing the registration form."""
    return AuthService(session).validate_educator_invite_token(token=token)


@router.post("/register-educator-invite", status_code=status.HTTP_201_CREATED)
def register_educator_invite(
    req: EducatorInviteRegisterRequest,
    request: Request,
    session: Session = Depends(get_db_session),
):
    """Register an educator via a one-time admin-issued invite link."""
    try:
        return AuthService(session).register_via_educator_invite(
            usr_name=req.userName,
            email=str(req.email),
            password=req.password,
            invite_token=req.inviteToken,
            public_frontend_base_url=resolve_public_frontend_base_url(request),
        )
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
