from __future__ import annotations

from collections.abc import Callable
import secrets

from fastapi import Header

from platform_common.auth.bearer import parse_bearer_token
from platform_common.auth.identity_client import fetch_identity_payload
from platform_common.errors import http_error, insufficient_permissions_error, invalid_identity_response_error
from platform_common.permissions.checker import extract_permission_codes


def build_require_identity_user(identity_service_url_getter: Callable[[], str]) -> Callable[[str | None], dict]:
    def dependency(authorization: str | None = Header(None)) -> dict:
        token = parse_bearer_token(authorization)
        current_user = fetch_identity_payload(
            identity_service_url=identity_service_url_getter(),
            token=token,
            path="/auth/me",
        )
        if "id" not in current_user:
            raise invalid_identity_response_error()
        return current_user

    return dependency


def build_require_identity_permission(
    permission_code: str,
    identity_service_url_getter: Callable[[], str],
) -> Callable[[str | None], dict]:
    def dependency(authorization: str | None = Header(None)) -> dict:
        token = parse_bearer_token(authorization)
        identity_service_url = identity_service_url_getter()
        current_user = fetch_identity_payload(
            identity_service_url=identity_service_url,
            token=token,
            path="/auth/me",
        )
        permissions_payload = fetch_identity_payload(
            identity_service_url=identity_service_url,
            token=token,
            path="/auth/me/permissions",
        )

        permission_codes = extract_permission_codes(permissions_payload)
        if permission_code not in permission_codes:
            raise insufficient_permissions_error()

        if "id" not in current_user:
            raise invalid_identity_response_error()

        current_user["permissions"] = sorted(permission_codes)
        return current_user

    return dependency


def build_require_internal_request(
    internal_token_getter: Callable[[], str],
    header_name: str = "X-Internal-Token",
) -> Callable[[str | None], None]:
    def dependency(internal_token: str | None = Header(None, alias=header_name)) -> None:
        expected_token = internal_token_getter()
        if not expected_token:
            raise http_error(
                status_code=503,
                code="INTERNAL_API_TOKEN_NOT_CONFIGURED",
                message="Internal API token is not configured",
            )
        if not internal_token or not secrets.compare_digest(internal_token, expected_token):
            raise http_error(
                status_code=403,
                code="INTERNAL_API_FORBIDDEN",
                message="Invalid internal API token",
            )

    return dependency
