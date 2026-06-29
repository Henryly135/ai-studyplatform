from __future__ import annotations

import base64
import hashlib
import hmac
import json

from fastapi import HTTPException

from platform_common.ids.types import ResourceKind

_PREFIXES: dict[ResourceKind, str] = {
    "comment": "cmt",
    "course": "crs",
    "forum_post": "pst",
    "module": "mod",
    "material": "mat",
    "notification": "ntf",
    "request": "req",
    "session": "ses",
    "user": "usr",
    "quiz": "qiz",
    "quiz_question": "qqn",
    "quiz_option": "qop",
    "quiz_attempt": "qat",
}


def _sign_payload(payload: str, *, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:12]).decode("utf-8").rstrip("=")


def encode_public_uuid(*, kind: ResourceKind, resource_id: int, secret: str) -> str:
    payload = json.dumps({"t": kind, "id": resource_id}, separators=(",", ":"))
    encoded_payload = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")
    signature = _sign_payload(payload, secret=secret)
    return f"{_PREFIXES[kind]}_{encoded_payload}.{signature}"


def decode_public_uuid(*, public_id: str, expected_kind: ResourceKind, secret: str) -> int:
    prefix = f"{_PREFIXES[expected_kind]}_"
    if not public_id.startswith(prefix) or "." not in public_id:
        raise HTTPException(status_code=400, detail=f"Invalid {expected_kind}Uuid.")

    encoded_payload, provided_signature = public_id[len(prefix) :].split(".", 1)
    padded_payload = encoded_payload + "=" * (-len(encoded_payload) % 4)

    try:
        payload = base64.urlsafe_b64decode(padded_payload.encode("utf-8")).decode("utf-8")
        parsed = json.loads(payload)
        resource_id = int(parsed["id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {expected_kind}Uuid.") from exc

    expected_signature = _sign_payload(payload, secret=secret)
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise HTTPException(status_code=400, detail=f"Invalid {expected_kind}Uuid.")

    if parsed.get("t") != expected_kind or resource_id < 1:
        raise HTTPException(status_code=400, detail=f"Invalid {expected_kind}Uuid.")

    return resource_id
