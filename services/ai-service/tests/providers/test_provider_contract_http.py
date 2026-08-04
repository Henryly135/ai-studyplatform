from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
import time

import pytest

from app.services.providers.adapters import (
    OpenAICompatibleChatAdapter,
    OpenAICompatibleEmbeddingAdapter,
)
from app.services.providers.types import (
    EmbeddingRequest,
    ProviderInvocationError,
    ProviderQuotaError,
    TextGenerationRequest,
)


class _ProviderContractServer(ThreadingHTTPServer):
    status_code = 200
    response_payload: dict = {}
    delay_seconds = 0.0
    requests: list[dict] = []


class _ProviderContractHandler(BaseHTTPRequestHandler):
    server: _ProviderContractServer

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        self.server.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "payload": json.loads(body.decode("utf-8")),
            }
        )
        if self.server.delay_seconds:
            time.sleep(self.server.delay_seconds)
        encoded = json.dumps(self.server.response_payload).encode("utf-8")
        try:
            self.send_response(self.server.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, _format: str, *_args) -> None:
        return


@pytest.fixture
def provider_server():
    server = _ProviderContractServer(("127.0.0.1", 0), _ProviderContractHandler)
    server.status_code = 200
    server.response_payload = {}
    server.delay_seconds = 0
    server.requests = []
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield server, f"http://{host}:{port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _chat_request(base_url: str, *, provider_key: str = "glm") -> TextGenerationRequest:
    return TextGenerationRequest(
        provider_key=provider_key,
        model_name="glm-4.7" if provider_key == "glm" else "openrouter/auto",
        api_key="contract-secret",
        base_url=base_url,
        prompt="hello",
        max_output_tokens=20,
    )


def test_openai_compatible_provider_success_contract_over_real_http(
    provider_server,
    monkeypatch,
) -> None:
    server, base_url = provider_server
    monkeypatch.setattr(
        "app.services.providers.adapters.settings",
        type(
            "Settings",
            (),
            {
                "ai_chat_timeout_seconds": 1,
                "ai_embedding_timeout_seconds": 1,
            },
        )(),
    )
    server.response_payload = {
        "choices": [
            {
                "message": {"content": "contract ok"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 2,
            "completion_tokens": 2,
            "total_tokens": 4,
        },
    }

    chat_result = OpenAICompatibleChatAdapter().generate_text(
        _chat_request(base_url)
    )

    assert chat_result.text == "contract ok"
    assert server.requests[0]["path"] == "/v1/chat/completions"
    assert server.requests[0]["authorization"] == "Bearer contract-secret"
    assert server.requests[0]["payload"]["model"] == "glm-4.7"

    server.response_payload = {
        "data": [{"index": 0, "embedding": [3, 4]}],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }
    embedding_result = OpenAICompatibleEmbeddingAdapter().embed(
        EmbeddingRequest(
            provider_key="glm",
            model_name="embedding-3",
            api_key="contract-secret",
            base_url=base_url,
            text="document",
            output_dimension=2,
        )
    )

    assert embedding_result.vector == pytest.approx([0.6, 0.8])
    assert server.requests[1]["path"] == "/v1/embeddings"
    assert server.requests[1]["payload"] == {
        "model": "embedding-3",
        "input": "document",
        "dimensions": 2,
    }


@pytest.mark.parametrize(
    ("status_code", "expected_exception", "expected_error_type"),
    [
        (401, ProviderInvocationError, "provider_authentication_error"),
        (402, ProviderQuotaError, None),
        (408, ProviderInvocationError, "provider_timeout"),
        (429, ProviderQuotaError, None),
        (500, ProviderInvocationError, "transient_network_error"),
        (503, ProviderInvocationError, "transient_network_error"),
        (504, ProviderInvocationError, "provider_timeout"),
    ],
)
def test_openai_compatible_provider_http_error_contract(
    provider_server,
    monkeypatch,
    status_code,
    expected_exception,
    expected_error_type,
) -> None:
    server, base_url = provider_server
    server.status_code = status_code
    server.response_payload = {
        "error": {
            "message": "upstream failure",
        }
    }
    monkeypatch.setattr(
        "app.services.providers.adapters.settings",
        type("Settings", (), {"ai_chat_timeout_seconds": 1})(),
    )

    with pytest.raises(expected_exception) as exc_info:
        OpenAICompatibleChatAdapter().generate_text(
            _chat_request(base_url, provider_key="openrouter")
        )

    if expected_error_type is not None:
        assert exc_info.value.provider_error_type == expected_error_type
    assert "contract-secret" not in str(exc_info.value)


def test_openrouter_http_200_error_body_contract(
    provider_server,
    monkeypatch,
) -> None:
    server, base_url = provider_server
    server.response_payload = {
        "error": {
            "code": 429,
            "message": "quota reached",
            "metadata": {"error_type": "rate_limit_exceeded"},
        }
    }
    monkeypatch.setattr(
        "app.services.providers.adapters.settings",
        type("Settings", (), {"ai_chat_timeout_seconds": 1})(),
    )

    with pytest.raises(ProviderQuotaError):
        OpenAICompatibleChatAdapter().generate_text(
            _chat_request(base_url, provider_key="openrouter")
        )


def test_openai_compatible_provider_timeout_contract(
    provider_server,
    monkeypatch,
) -> None:
    server, base_url = provider_server
    server.delay_seconds = 0.1
    server.response_payload = {
        "choices": [{"message": {"content": "too late"}}]
    }
    monkeypatch.setattr(
        "app.services.providers.adapters.settings",
        type("Settings", (), {"ai_chat_timeout_seconds": 0.01})(),
    )

    with pytest.raises(
        ProviderInvocationError,
    ) as exc_info:
        OpenAICompatibleChatAdapter().generate_text(
            _chat_request(base_url)
        )

    assert exc_info.value.provider_error_type == "provider_timeout"
