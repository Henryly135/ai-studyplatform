import logging
import hmac
import os
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.public_url import (
    PublicFrontendUrlNotConfiguredError,
    configured_public_frontend_base_url,
    normalize_public_frontend_base_url,
    resolve_trusted_public_frontend_base_url,
)
from app.core.security import hash_token
from app.db.session import get_db_session
from app.schemas.admin import (
    EducatorApprovalListResponse,
    EducatorApprovalHistoryQuery,
    EducatorApprovalRead,
    EducatorInviteTokenGenerateResponse,
    EducatorInviteTokenListResponse,
    EducatorInviteTokenRead,
    EmailDeliveryStatus,
    AdminUserListResponse,
    AdminUserRead,
    ReviewEducatorApprovalRequest,
    SendEducatorInviteEmailRequest,
    SendEducatorInviteEmailResponse,
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

logger = logging.getLogger(__name__)

_INVITE_LINK_CONFIGURATION_UNAVAILABLE = "Invite link generation is temporarily unavailable."


def _trusted_invite_frontend_base_url(request: Request) -> str | None:
    try:
        return resolve_trusted_public_frontend_base_url(request)
    except PublicFrontendUrlNotConfiguredError as exc:
        logger.error("Trusted public frontend URL is unavailable for educator invite link generation")
        raise HTTPException(status_code=500, detail=_INVITE_LINK_CONFIGURATION_UNAVAILABLE) from exc


def _build_invite_url(raw_token: str, frontend_base_url: str | None = None) -> str:
    if frontend_base_url:
        base = normalize_public_frontend_base_url(frontend_base_url) or frontend_base_url.rstrip("/")
    else:
        configured = configured_public_frontend_base_url()
        if configured:
            base = configured
        else:
            nginx_port = os.getenv("NGINX_PORT")
            base = f"http://localhost:{nginx_port}" if nginx_port else "http://localhost:5173"
    qs = urlencode({"token": raw_token})
    return f"{base}/register/educator-invite?{qs}"


def _validated_invite_email_url(
    invite_url: str,
    *,
    expected_token_hash: str,
    frontend_base_url: str | None,
) -> str:
    parsed = urlparse(invite_url)
    expected = urlparse(_build_invite_url("__token__", frontend_base_url=frontend_base_url))

    if (
        parsed.scheme != expected.scheme
        or parsed.netloc.lower() != expected.netloc.lower()
        or parsed.path != expected.path
        or parsed.fragment
    ):
        raise HTTPException(status_code=400, detail="Invite URL does not match this platform")

    params = parse_qs(parsed.query, keep_blank_values=True)
    token_values = params.get("token", [])
    if set(params.keys()) != {"token"} or len(token_values) != 1:
        raise HTTPException(status_code=400, detail="Invite URL token is invalid")

    if not hmac.compare_digest(hash_token(token_values[0]), expected_token_hash):
        raise HTTPException(status_code=400, detail="Invite URL token does not match this invite")

    return invite_url


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
    frontend_base_url = _trusted_invite_frontend_base_url(request)
    result = AuthService(session).generate_educator_invite_token(
        created_by_user_id=int(current_user["id"]),
    )
    invite_url = _build_invite_url(
        result["rawToken"],
        frontend_base_url=frontend_base_url,
    )
    return EducatorInviteTokenGenerateResponse(
        inviteUuid=result["inviteUuid"],
        rawToken=result["rawToken"],
        expiresAt=result["expiresAt"],
        inviteUrl=invite_url,
    )


def _invite_email_detail(delivered: bool, reason: str | None) -> str:
    if delivered:
        return "Invite email sent"
    if reason == "smtp_not_configured":
        return "Invite email was not sent because SMTP is not configured"
    if reason == "invalid_smtp_port":
        return "Invite email was not sent because SMTP_PORT is invalid"
    return "Invite email could not be delivered"


@router.post(
    "/educator-invite-tokens/{invite_uuid}/send-email",
    response_model=SendEducatorInviteEmailResponse,
)
def send_educator_invite_email_endpoint(
    invite_uuid: str,
    payload: SendEducatorInviteEmailRequest,
    request: Request,
    current_user: dict = Depends(require_permission(EDUCATOR_APPROVAL_REVIEW)),
    session: Session = Depends(get_db_session),
) -> SendEducatorInviteEmailResponse:
    """Send the educator invite link (with the raw token URL) to a specific email address."""
    from app.core.email import send_educator_invite_email as _send_invite_email

    repo = EducatorInviteTokenRepository(session)
    token = repo.get_by_uuid(invite_uuid)
    if not token:
        raise HTTPException(status_code=404, detail="Invite token not found")
    if token.created_by_user_id != int(current_user["id"]):
        raise HTTPException(status_code=403, detail="Not authorised to send this invite")
    if token.used_at is not None:
        raise HTTPException(status_code=409, detail="Invite link has already been used")

    invite_url = _validated_invite_email_url(
        payload.inviteUrl,
        expected_token_hash=token.token_hash,
        frontend_base_url=_trusted_invite_frontend_base_url(request),
    )
    delivery = _send_invite_email(str(payload.recipientEmail), invite_url)
    return SendEducatorInviteEmailResponse(
        detail=_invite_email_detail(delivery.delivered, delivery.reason),
        emailDelivery=EmailDeliveryStatus(
            attempted=delivery.attempted,
            delivered=delivery.delivered,
            reason=delivery.reason,
        ),
    )


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
