import os

from platform_common.config.env import load_project_env


def test_load_project_env_strips_inline_comments(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("SERVICE_PORT=8001 # local ai service port\n", encoding="utf-8")
    nested_path = tmp_path / "services" / "ai-service"
    nested_path.mkdir(parents=True)
    monkeypatch.delenv("SERVICE_PORT", raising=False)

    load_project_env(nested_path / "app.py")

    assert os.environ["SERVICE_PORT"] == "8001"


def test_load_project_env_preserves_hash_inside_quoted_values(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                'TOKEN="abc#123"',
                "PASSWORD='p#s'",
            ]
        ),
        encoding="utf-8",
    )
    nested_path = tmp_path / "services" / "ai-service"
    nested_path.mkdir(parents=True)
    monkeypatch.delenv("TOKEN", raising=False)
    monkeypatch.delenv("PASSWORD", raising=False)

    load_project_env(nested_path / "app.py")

    assert os.environ["TOKEN"] == "abc#123"
    assert os.environ["PASSWORD"] == "p#s"


def test_load_project_env_preserves_unquoted_hash_without_leading_space(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("CALLBACK_URL=https://example.com/callback#section\n", encoding="utf-8")
    nested_path = tmp_path / "services" / "ai-service"
    nested_path.mkdir(parents=True)
    monkeypatch.delenv("CALLBACK_URL", raising=False)

    load_project_env(nested_path / "app.py")

    assert os.environ["CALLBACK_URL"] == "https://example.com/callback#section"


def test_load_project_env_does_not_override_existing_env(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("AI_CHAT_PROVIDER=gemini\n", encoding="utf-8")
    nested_path = tmp_path / "services" / "ai-service"
    nested_path.mkdir(parents=True)
    monkeypatch.setenv("AI_CHAT_PROVIDER", "deepseek")

    load_project_env(nested_path / "app.py")

    assert os.environ["AI_CHAT_PROVIDER"] == "deepseek"
