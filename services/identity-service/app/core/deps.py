from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db_session
from app.services.auth_service import AuthServiceError
from platform_common.auth import build_require_internal_request
from platform_common.auth.bearer import parse_bearer_token as shared_parse_bearer_token
from platform_common.errors import insufficient_permissions_error
from platform_common.permissions.checker import extract_permission_codes


def parse_bearer_token(authorization: str | None) -> str:
    try:
        return shared_parse_bearer_token(authorization)
    except HTTPException as exc:
        raise HTTPException(status_code=exc.status_code, detail="Invalid credentials") from exc


def require_auth(
    authorization: str | None = Header(None),
    session: Session = Depends(get_db_session),
) -> dict:
    from app.services.auth_service import AuthService

    token = parse_bearer_token(authorization)
    try:
        return AuthService(session).get_current_user(token)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def require_access_token(authorization: str | None = Header(None)) -> str:
    return parse_bearer_token(authorization)


def require_permission(permission_code: str):
    def dependency(
        token: str = Depends(require_access_token),
        session: Session = Depends(get_db_session),
    ) -> dict:
        from app.services.auth_service import AuthService

        try:
            auth_service = AuthService(session)
            current_user = auth_service.get_current_user(token)
            permission_response = auth_service.get_current_user_permissions(token)
        except AuthServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        permission_codes = extract_permission_codes(permission_response)
        if permission_code not in permission_codes:
            raise insufficient_permissions_error()

        current_user["permissions"] = sorted(permission_codes)
        return current_user

    return dependency


require_internal_request = build_require_internal_request(lambda: settings.internal_api_token)
