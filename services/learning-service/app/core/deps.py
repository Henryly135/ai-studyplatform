from collections.abc import Callable

from fastapi import Header

from app.core.config import settings
from platform_common.auth import (
    build_require_identity_permission,
    build_require_identity_user,
    build_require_internal_request,
)


def require_identity_permission(permission_code: str) -> Callable[[str | None], dict]:
    return build_require_identity_permission(permission_code, lambda: settings.identity_service_url)


def require_identity_user(authorization: str | None = Header(None)) -> dict:
    dependency = build_require_identity_user(lambda: settings.identity_service_url)
    return dependency(authorization)


require_internal_request = build_require_internal_request(lambda: settings.internal_api_token)
