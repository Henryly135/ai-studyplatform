from collections.abc import Callable

from fastapi import Header, Response

from app.core.config import settings
from app.services.material_access_session import set_material_access_session_cookie
from platform_common.auth import (
    build_require_identity_permission,
    build_require_identity_user,
    build_require_internal_request,
)


def require_identity_permission(permission_code: str) -> Callable[[str | None], dict]:
    base_dependency = build_require_identity_permission(permission_code, lambda: settings.identity_service_url)

    def dependency(response: Response, authorization: str | None = Header(None)) -> dict:
        current_user = base_dependency(authorization)
        set_material_access_session_cookie(response, current_user)
        return current_user

    return dependency


def require_identity_user(response: Response, authorization: str | None = Header(None)) -> dict:
    dependency = build_require_identity_user(lambda: settings.identity_service_url)
    current_user = dependency(authorization)
    set_material_access_session_cookie(response, current_user)
    return current_user


require_internal_request = build_require_internal_request(lambda: settings.internal_api_token)
