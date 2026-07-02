import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from urllib.parse import urlparse


LOCAL_CORS_ALLOWED_ORIGINS = (
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
PRODUCTION_ENVIRONMENTS = {"prod", "production"}
LOCAL_CORS_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
COMMON_PLACEHOLDER_VALUES = {
    "",
    "change-me",
    "change_me",
    "changeme",
    "password",
    "secret",
    "app_password",
    "ai_password",
    "change_me_internal_api_token",
    "change-me-in-production-use-a-long-random-string",
    "replace_with_a_random_64_char_hex_string",
    "your-gemini-api-key",
    "your-admin-password",
    "minioadmin",
}
COMMON_PLACEHOLDER_PREFIXES = (
    "change_me",
    "change-me",
    "replace_with",
    "your-",
)


def load_project_env(start_path: str | Path) -> None:
    current_path = Path(start_path).resolve()
    env_path = None
    for parent in current_path.parents:
        candidate = parent / ".env"
        if candidate.exists():
            env_path = candidate
            break
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def _strip_inline_comment(value: str) -> str:
    active_quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue

        if character == "\\" and active_quote == '"':
            escaped = True
            continue

        if character in {"'", '"'}:
            if active_quote is None:
                active_quote = character
            elif active_quote == character:
                active_quote = None
            continue

        if character == "#" and active_quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()

    return value.strip()


def get_env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def get_csv_env(*names: str, default: str) -> tuple[str, ...]:
    return parse_csv(get_env(*names, default=default))


def is_production_environment(value: str | None = None) -> bool:
    app_env = value if value is not None else get_env("APP_ENV", default="local")
    return app_env.strip().lower() in PRODUCTION_ENVIRONMENTS


def get_cors_allowed_origins() -> tuple[str, ...]:
    configured = get_csv_env("CORS_ALLOWED_ORIGINS", default="")
    if configured:
        if "*" in configured:
            raise ValueError("CORS_ALLOWED_ORIGINS must not contain '*'")
        return configured

    if is_production_environment():
        return ()

    return LOCAL_CORS_ALLOWED_ORIGINS


def is_placeholder_secret(value: str | None, forbidden_values: Iterable[str] = ()) -> bool:
    if value is None:
        return True

    normalized = value.strip().strip("'\"").strip().lower()
    if normalized in COMMON_PLACEHOLDER_VALUES:
        return True

    forbidden_normalized = {item.strip().strip("'\"").strip().lower() for item in forbidden_values}
    if normalized in forbidden_normalized:
        return True

    return any(normalized.startswith(prefix) for prefix in COMMON_PLACEHOLDER_PREFIXES)


def _is_local_origin(origin: str) -> bool:
    parsed = urlparse(origin.strip())
    host = parsed.hostname or origin.strip().split(":", 1)[0]
    return host.strip("[]").lower() in LOCAL_CORS_HOSTS


def validate_production_security_config(
    *,
    service_name: str,
    cors_allowed_origins: tuple[str, ...] | None = None,
    required_values: Mapping[str, str | None] | None = None,
    forbidden_values: Mapping[str, Iterable[str]] | None = None,
    min_lengths: Mapping[str, int] | None = None,
    public_urls: Mapping[str, str | None] | None = None,
) -> None:
    if not is_production_environment():
        return

    errors: list[str] = []
    if cors_allowed_origins is not None:
        if not cors_allowed_origins:
            errors.append("CORS_ALLOWED_ORIGINS must be configured in production")
        local_origins = [origin for origin in cors_allowed_origins if _is_local_origin(origin)]
        if local_origins:
            errors.append("CORS_ALLOWED_ORIGINS must not contain local development origins in production")

    required_values = required_values or {}
    forbidden_values = forbidden_values or {}
    min_lengths = min_lengths or {}
    public_urls = public_urls or {}
    for name, value in required_values.items():
        if value is None or not value.strip():
            errors.append(f"{name} must be configured in production")
            continue

        if is_placeholder_secret(value, forbidden_values.get(name, ())):
            errors.append(f"{name} must not use a placeholder/default value in production")

        min_length = min_lengths.get(name)
        if min_length is not None and len(value.strip()) < min_length:
            errors.append(f"{name} must be at least {min_length} characters in production")

    for name, value in public_urls.items():
        if value is None or not value.strip():
            errors.append(f"{name} must be configured in production")
            continue

        normalized = value.strip().strip("'\"").strip()
        if is_placeholder_secret(normalized, forbidden_values.get(name, ())):
            errors.append(f"{name} must not use a placeholder/default value in production")
            continue

        parsed = urlparse(normalized)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{name} must be an absolute HTTPS URL in production")
            continue

        if _is_local_origin(normalized):
            errors.append(f"{name} must not use local development hosts in production")

    if errors:
        raise ValueError(f"{service_name} production configuration is unsafe: {'; '.join(errors)}")
