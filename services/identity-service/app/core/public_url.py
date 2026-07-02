import os
from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit

from fastapi import Request


class PublicFrontendUrlNotConfiguredError(RuntimeError):
    pass


def _default_public_frontend_port() -> str | None:
    port = (os.getenv("PUBLIC_FRONTEND_PORT") or os.getenv("NGINX_PORT") or "").strip()
    return port or None


def _should_append_public_port(hostname: str | None) -> bool:
    if not hostname:
        return False

    normalized_host = hostname.strip("[]").lower()
    if normalized_host == "localhost":
        return True

    try:
        ip_address(normalized_host)
    except ValueError:
        return False

    return True


def normalize_public_frontend_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None

    candidate = base_url.strip().rstrip("/")
    if not candidate:
        return None

    parsed = urlsplit(candidate)
    if not parsed.scheme or not parsed.netloc:
        return candidate

    if parsed.port is not None or not _should_append_public_port(parsed.hostname):
        return candidate

    port = _default_public_frontend_port()
    if not port:
        return candidate

    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo += f":{parsed.password}"
        userinfo += "@"

    netloc = f"{userinfo}{hostname}:{port}"
    return urlunsplit(parsed._replace(netloc=netloc)).rstrip("/")


def configured_public_frontend_base_url() -> str | None:
    explicit = (os.getenv("PUBLIC_FRONTEND_URL") or "").strip()
    if explicit:
        return normalize_public_frontend_base_url(explicit) or explicit.rstrip("/")

    public_base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if public_base:
        if public_base.endswith("/api"):
            public_base = public_base[:-4]
        return normalize_public_frontend_base_url(public_base) or public_base

    return None


def resolve_public_frontend_base_url(request: Request) -> str | None:
    explicit = (request.headers.get("x-public-frontend-url") or "").strip()
    if explicit:
        return normalize_public_frontend_base_url(explicit)

    origin = (request.headers.get("origin") or "").strip()
    if origin.startswith(("http://", "https://")):
        return normalize_public_frontend_base_url(origin)

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    scheme = forwarded_proto or request.url.scheme or "http"
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    host = forwarded_host or (request.headers.get("host") or "").strip()
    if host:
        return normalize_public_frontend_base_url(f"{scheme}://{host}")

    return None


def resolve_trusted_public_frontend_base_url(request: Request) -> str | None:
    configured = configured_public_frontend_base_url()
    if configured:
        return configured

    if os.getenv("APP_ENV", "").strip().lower() == "production":
        raise PublicFrontendUrlNotConfiguredError("Public frontend URL is not configured")

    return resolve_public_frontend_base_url(request)
