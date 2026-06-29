from __future__ import annotations

import json
from urllib import error, request

from fastapi import HTTPException

from platform_common.errors import http_error


def post_json(
    *,
    url: str,
    payload: dict[str, object],
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> dict[str, object]:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail: dict[str, object] | str = "Request failed"
        try:
            raw_body = exc.read().decode("utf-8")
            parsed_body = json.loads(raw_body) if raw_body else {}
            detail = parsed_body.get("error") or parsed_body.get("detail") or detail
        except Exception:
            pass

        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            raise HTTPException(status_code=exc.code, detail=detail) from exc

        raise http_error(
            status_code=exc.code,
            code="UPSTREAM_HTTP_ERROR",
            message=str(detail),
        ) from exc
    except error.URLError as exc:
        raise http_error(
            status_code=503,
            code="UPSTREAM_SERVICE_UNAVAILABLE",
            message="Upstream service is unavailable",
        ) from exc

    if not body:
        return {}

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise http_error(
            status_code=502,
            code="INVALID_UPSTREAM_RESPONSE",
            message="Upstream service returned invalid JSON",
        ) from exc

    if not isinstance(parsed, dict):
        raise http_error(
            status_code=502,
            code="INVALID_UPSTREAM_RESPONSE",
            message="Upstream service returned an unexpected response body",
        )

    return parsed


def get_json(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> dict[str, object]:
    req = request.Request(
        url=url,
        headers=headers or {},
        method="GET",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail: dict[str, object] | str = "Request failed"
        try:
            raw_body = exc.read().decode("utf-8")
            parsed_body = json.loads(raw_body) if raw_body else {}
            detail = parsed_body.get("error") or parsed_body.get("detail") or detail
        except Exception:
            pass

        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            raise HTTPException(status_code=exc.code, detail=detail) from exc

        raise http_error(
            status_code=exc.code,
            code="UPSTREAM_HTTP_ERROR",
            message=str(detail),
        ) from exc
    except error.URLError as exc:
        raise http_error(
            status_code=503,
            code="UPSTREAM_SERVICE_UNAVAILABLE",
            message="Upstream service is unavailable",
        ) from exc

    if not body:
        return {}

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise http_error(
            status_code=502,
            code="INVALID_UPSTREAM_RESPONSE",
            message="Upstream service returned invalid JSON",
        ) from exc

    if not isinstance(parsed, dict):
        raise http_error(
            status_code=502,
            code="INVALID_UPSTREAM_RESPONSE",
            message="Upstream service returned an unexpected response body",
        )

    return parsed
