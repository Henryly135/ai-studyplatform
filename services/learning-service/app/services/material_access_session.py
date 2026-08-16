from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass

from fastapi import Response

from app.core.config import settings
from platform_common.ids.secret import get_public_id_secret


MATERIAL_ACCESS_SESSION_COOKIE = "material_access_session"


@dataclass(frozen=True)
class MaterialAccessSessionGrant:
    user_id: int
    identity: str
    expires_at: int


def _encode_payload(payload: str) -> str:
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_payload(payload: str) -> str:
    padded = payload + "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")


def _sign_payload(encoded_payload: str) -> str:
    secret = get_public_id_secret(settings.public_id_secret)
    message = f"material-access-session:{encoded_payload}"
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def create_material_access_session(
    *,
    user_id: int,
    identity: str,
    expires_at: int | None = None,
) -> str:
    normalized_identity = identity.strip()
    if user_id < 1 or not normalized_identity or ":" in normalized_identity:
        raise ValueError("Material access session subject is invalid")
    resolved_expiry = expires_at or (
        int(time.time()) + max(1, settings.material_access_url_expires_seconds)
    )
    encoded_payload = _encode_payload(f"{user_id}:{normalized_identity}:{resolved_expiry}")
    return f"{encoded_payload}.{_sign_payload(encoded_payload)}"


def validate_material_access_session(token: str | None) -> MaterialAccessSessionGrant:
    if not token or "." not in token:
        raise ValueError("Material access session is required")
    encoded_payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign_payload(encoded_payload)):
        raise ValueError("Material access session is invalid")
    try:
        user_id_text, identity, expires_text = _decode_payload(encoded_payload).split(":", 2)
        user_id = int(user_id_text)
        expires_at = int(expires_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Material access session is invalid") from exc
    if user_id < 1 or not identity or expires_at < int(time.time()):
        raise ValueError("Material access session has expired")
    return MaterialAccessSessionGrant(user_id=user_id, identity=identity, expires_at=expires_at)


def require_matching_material_access_session(
    *,
    token: str | None,
    user_id: int,
    identity: str,
) -> MaterialAccessSessionGrant:
    grant = validate_material_access_session(token)
    if grant.user_id != user_id or grant.identity != identity.strip():
        raise ValueError("Material access session does not match this URL")
    return grant


def set_material_access_session_cookie(response: Response, current_user: dict) -> None:
    user_id = current_user.get("id")
    identity = current_user.get("identity")
    if not isinstance(user_id, int) or not isinstance(identity, str) or not identity.strip():
        return
    max_age = max(1, settings.material_access_url_expires_seconds)
    response.set_cookie(
        key=MATERIAL_ACCESS_SESSION_COOKIE,
        value=create_material_access_session(user_id=user_id, identity=identity),
        max_age=max_age,
        httponly=True,
        secure=str(getattr(settings, "public_base_url", "")).lower().startswith("https://"),
        samesite="strict",
        path="/",
    )
