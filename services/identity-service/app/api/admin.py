import os
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.public_url import normalize_public_frontend_base_url, resolve_public_frontend_base_url
from app.db.session import get_db_session
from app.schemas.admin import (
    EducatorApprovalListResponse,
    EducatorApprovalHistoryQuery,
    EducatorApprovalRead,
    EducatorInviteTokenGenerateResponse,
    EducatorInviteTokenListResponse,
    EducatorInviteTokenRead,
    AdminUserListResponse,
    AdminUserRead,
    ReviewEducatorApprovalRequest,
    SendEducatorInviteEmailRequest,
    UpdateUserIdentityRequest,
    UpdateUserStatusRequest,
)
from app.services.approval_service import ApprovalService
from app.services.approval_service import ApprovalServiceError
from app.services.admin_user_service import AdminUserService
from app.services.admin_user_service import AdminUserServiceError
from app.services.auth_service import AuthService
from app.repositories.educator_invite_token_repository import EducatorInviteTokenRepository
from platform_common.permissions.codes import EDUCATOR_APPROVAL_READ, EDUCATOR_APPROVAL_REVIEW, USER_READ, USER_UPDATE


def _build_invite_url(raw_token: str, frontend_base_url: str | None = None) -> str:
    if frontend_base_url:
        base = normalize_public_frontend_base_url(frontend_base_url) or frontend_base_url.rstrip("/")
    else:
        explicit = os.getenv("PUBLIC_FRONTEND_URL")
        public_base = os.getenv("PUBLIC_BASE_URL", "")
        if explicit:
            base = normalize_public_frontend_base_url(explicit) or explicit.rstrip("/")
        elif public_base:
            if public_base.endswith("/api"):
                base = public_base[:-4]
            else:
                base = public_base.rstrip("/")
            base = normalize_public_frontend_base_url(base) or base
        else:
            nginx_port = os.getenv("NGINX_PORT")
            base = f"http://localhost:{nginx_port}" if nginx_port else "http://localhost:5173"
    qs = urlencode({"token": raw_token})
    return f"{base}/register/educator-invite?{qs}"

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    current_user: dict = Depends(require_permission(USER_READ)),
    session: Session = Depends(get_db_session),
) -> AdminUserListResponse:
    _ = current_user
    return AdminUserService(session).list_users()


@router.patch("/users/{user_uuid}/identity", response_model=AdminUserRead)
def update_user_identity(
    user_uuid: str,
    payload: UpdateUserIdentityRequest,
    current_user: dict = Depends(require_permission(USER_UPDATE)),
    session: Session = Depends(get_db_session),
) -> AdminUserRead:
    try:
        return AdminUserService(session).update_user_identity(
            user_uuid=user_uuid,
            identity=payload.identity,
            changed_by_user_id=int(current_user["id"]),
        )
    except AdminUserServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.patch("/users/{user_uuid}/status", response_model=AdminUserRead)
def update_user_status(
    user_uuid: str,
    payload: UpdateUserStatusRequest,
    current_user: dict = Depends(require_permission(USER_UPDATE)),
    session: Session = Depends(get_db_session),
) -> AdminUserRead:
    try:
        return AdminUserService(session).update_user_status(
            user_uuid=user_uuid,
            account_status=payload.accountStatus,
            changed_by_user_id=int(current_user["id"]),
        )
    except AdminUserServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/educator-approvals", response_model=EducatorApprovalListResponse)
def list_educator_approvals(
    current_user: dict = Depends(require_permission(EDUCATOR_APPROVAL_READ)),
    session: Session = Depends(get_db_session),
) -> EducatorApprovalListResponse:
    _ = current_user
    return ApprovalService(session).list_requests()


@router.get("/educator-approvals/history", response_model=EducatorApprovalListResponse)
def list_reviewed_educator_approvals(
    query: EducatorApprovalHistoryQuery = Depends(),
    current_user: dict = Depends(require_permission(EDUCATOR_APPROVAL_READ)),
    session: Session = Depends(get_db_session),
) -> EducatorApprovalListResponse:
    _ = current_user
    try:
        return ApprovalService(session).list_reviewed_requests(status=query.status)
    except ApprovalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/educator-approvals/{request_uuid}", response_model=EducatorApprovalRead)
def get_educator_approval(
    request_uuid: str,
    current_user: dict = Depends(require_permission(EDUCATOR_APPROVAL_READ)),
    session: Session = Depends(get_db_session),
) -> EducatorApprovalRead:
    _ = current_user
    try:
        return ApprovalService(session).get_request_by_uuid(request_uuid)
    except ApprovalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.patch("/educator-approvals/{request_uuid}", response_model=EducatorApprovalRead)
def review_educator_approval(
    request_uuid: str,
    payload: ReviewEducatorApprovalRequest,
    current_user: dict = Depends(require_permission(EDUCATOR_APPROVAL_REVIEW)),
    session: Session = Depends(get_db_session),
) -> EducatorApprovalRead:
    try:
        return ApprovalService(session).review_request_by_uuid(
            request_uuid=request_uuid,
            action=payload.action,
            review_comment=payload.reviewComment,
            reviewed_by_user_id=int(current_user["id"]),
        )
    except ApprovalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/educator-invite-tokens", response_model=EducatorInviteTokenGenerateResponse)
def generate_educator_invite_token(
    request: Request,
    current_user: dict = Depends(require_permission(EDUCATOR_APPROVAL_REVIEW)),
    session: Session = Depends(get_db_session),
) -> EducatorInviteTokenGenerateResponse:
    """Generate a one-time educator invite link. Only admins can call this."""
    result = AuthService(session).generate_educator_invite_token(
        created_by_user_id=int(current_user["id"]),
    )
    invite_url = _build_invite_url(
        result["rawToken"],
        frontend_base_url=resolve_public_frontend_base_url(request),
    )
    return EducatorInviteTokenGenerateResponse(
        inviteUuid=result["inviteUuid"],
        rawToken=result["rawToken"],
        expiresAt=result["expiresAt"],
        inviteUrl=invite_url,
    )


@router.post("/educator-invite-tokens/{invite_uuid}/send-email")
def send_educator_invite_email_endpoint(
    invite_uuid: str,
    payload: SendEducatorInviteEmailRequest,
    current_user: dict = Depends(require_permission(EDUCATOR_APPROVAL_REVIEW)),
    session: Session = Depends(get_db_session),
):
    """Send the educator invite link (with the raw token URL) to a specific email address."""
    from app.core.email import send_educator_invite_email as _send_invite_email
    from app.repositories.educator_invite_token_repository import EducatorInviteTokenRepository

    repo = EducatorInviteTokenRepository(session)
    token = repo.get_by_uuid(invite_uuid)
    if not token:
        raise HTTPException(status_code=404, detail="Invite token not found")
    if token.created_by_user_id != int(current_user["id"]):
        raise HTTPException(status_code=403, detail="Not authorised to send this invite")
    if token.used_at is not None:
        raise HTTPException(status_code=409, detail="Invite link has already been used")

    _send_invite_email(str(payload.recipientEmail), payload.inviteUrl)
    return {"detail": "Invite email sent"}


@router.get("/educator-invite-tokens", response_model=EducatorInviteTokenListResponse)
def list_educator_invite_tokens(
    current_user: dict = Depends(require_permission(EDUCATOR_APPROVAL_REVIEW)),
    session: Session = Depends(get_db_session),
) -> EducatorInviteTokenListResponse:
    """List invite tokens created by this admin."""
    repo = EducatorInviteTokenRepository(session)
    tokens = repo.list_by_creator(int(current_user["id"]))
    from app.core.time import now_local
    now = now_local()
    return EducatorInviteTokenListResponse(
        tokens=[
            EducatorInviteTokenRead(
                inviteUuid=t.invite_uuid,
                createdAt=t.created_at.isoformat(),
                expiresAt=t.expires_at.isoformat(),
                usedAt=t.used_at.isoformat() if t.used_at else None,
                isUsed=t.used_at is not None or t.expires_at < now,
            )
            for t in tokens
        ]
    )
