import os

import pytest

from platform_common.config.env import get_cors_allowed_origins, load_project_env, validate_production_security_config


def test_cors_allowed_origins_default_to_local_development(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    origins = get_cors_allowed_origins()

    assert "http://localhost:8080" in origins
    assert "http://127.0.0.1:5173" in origins


def test_cors_allowed_origins_are_empty_in_production_when_unconfigured(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert get_cors_allowed_origins() == ()


def test_cors_allowed_origins_reject_wildcard(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example,*")

    with pytest.raises(ValueError, match="must not contain"):
        get_cors_allowed_origins()


def test_cors_allowed_origins_parse_explicit_allowlist(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example, https://admin.example")

    assert get_cors_allowed_origins() == ("https://app.example", "https://admin.example")


def test_load_project_env_strips_unquoted_inline_comments(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "IDENTITY_PORT=8000                                                 # May have to Change",
                "JWT_SECRET_KEY=replace_with_a_random_64_char_hex_string         # Have to Change",
                "PASSWORD_WITH_HASH=abc#123",
                'QUOTED_VALUE="value # still data" # comment',
            ]
        ),
        encoding="utf-8",
    )
    nested_file = tmp_path / "service" / "app" / "config.py"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("", encoding="utf-8")
    for name in ("IDENTITY_PORT", "JWT_SECRET_KEY", "PASSWORD_WITH_HASH", "QUOTED_VALUE"):
        monkeypatch.delenv(name, raising=False)

    load_project_env(nested_file)

    assert os.getenv("IDENTITY_PORT") == "8000"
    assert os.getenv("JWT_SECRET_KEY") == "replace_with_a_random_64_char_hex_string"
    assert os.getenv("PASSWORD_WITH_HASH") == "abc#123"
    assert os.getenv("QUOTED_VALUE") == "value # still data"


def test_load_project_env_does_not_override_existing_values(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("APP_ENV=production # would be unsafe locally", encoding="utf-8")
    nested_file = tmp_path / "service" / "config.py"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "local")

    load_project_env(nested_file)

    assert os.getenv("APP_ENV") == "local"


def test_production_security_config_accepts_explicit_safe_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    validate_production_security_config(
        service_name="test-service",
        cors_allowed_origins=("https://app.example.com",),
        required_values={
            "JWT_SECRET_KEY": "x" * 64,
            "INTERNAL_API_TOKEN": "token-" + ("y" * 40),
        },
        min_lengths={"JWT_SECRET_KEY": 32, "INTERNAL_API_TOKEN": 32},
        public_urls={"PUBLIC_FRONTEND_URL": "https://app.example.com"},
    )


def test_production_security_config_rejects_missing_cors(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
        validate_production_security_config(
            service_name="test-service",
            cors_allowed_origins=(),
            required_values={"JWT_SECRET_KEY": "x" * 64},
        )


def test_production_security_config_rejects_local_cors(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(ValueError, match="local development origins"):
        validate_production_security_config(
            service_name="test-service",
            cors_allowed_origins=("https://app.example.com", "http://localhost:8080"),
            required_values={"JWT_SECRET_KEY": "x" * 64},
        )


def test_production_security_config_rejects_placeholder_and_short_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(ValueError) as error:
        validate_production_security_config(
            service_name="test-service",
            cors_allowed_origins=("https://app.example.com",),
            required_values={
                "JWT_SECRET_KEY": "replace_with_a_random_64_char_hex_string",
                "INTERNAL_API_TOKEN": "short",
            },
            min_lengths={"JWT_SECRET_KEY": 32, "INTERNAL_API_TOKEN": 32},
        )

    message = str(error.value)
    assert "JWT_SECRET_KEY must not use a placeholder" in message
    assert "INTERNAL_API_TOKEN must be at least 32 characters" in message


def test_production_security_config_rejects_unsafe_public_urls(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(ValueError) as error:
        validate_production_security_config(
            service_name="test-service",
            cors_allowed_origins=("https://app.example.com",),
            public_urls={
                "MISSING_PUBLIC_URL": "",
                "LOCAL_PUBLIC_URL": "https://localhost:8080",
                "HTTP_PUBLIC_URL": "http://app.example.com",
            },
        )

    message = str(error.value)
    assert "MISSING_PUBLIC_URL must be configured" in message
    assert "LOCAL_PUBLIC_URL must not use local development hosts" in message
    assert "HTTP_PUBLIC_URL must be an absolute HTTPS URL" in message


def test_production_security_config_is_noop_for_local_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")

    validate_production_security_config(
        service_name="test-service",
        cors_allowed_origins=("http://localhost:8080",),
        required_values={
            "JWT_SECRET_KEY": "replace_with_a_random_64_char_hex_string",
            "INTERNAL_API_TOKEN": "short",
        },
        min_lengths={"JWT_SECRET_KEY": 32, "INTERNAL_API_TOKEN": 32},
    )
