from __future__ import annotations

import json
from urllib import error, request

from fastapi import HTTPException

from platform_common.errors import (
    identity_service_unavailable_error,
    invalid_credentials_error,
    invalid_identity_response_error,
)


def fetch_identity_payload(*, identity_service_url: str, token: str, path: str) -> dict:
    req = request.Request(
        url=f"{identity_service_url}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with request.urlopen(req, timeout=10) as response:
            payload = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = "Invalid credentials"
        try:
            body = exc.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            detail = parsed.get("detail", detail)
        except Exception:
            pass
        message = detail["message"] if isinstance(detail, dict) and "message" in detail else str(detail)
        if exc.code == 401:
            raise invalid_credentials_error(message) from exc
        raise HTTPException(status_code=exc.code, detail={"code": "INVALID_CREDENTIALS", "message": message}) from exc
    except error.URLError as exc:
        raise identity_service_unavailable_error() from exc

    try:
        parsed_payload = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise invalid_identity_response_error() from exc

    if not isinstance(parsed_payload, dict):
        raise invalid_identity_response_error()

    return parsed_payload
