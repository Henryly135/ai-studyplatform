from __future__ import annotations

import json
import socket
from urllib import error, request as urllib_request

from app.services.providers.types import (
    AIProviderConfigurationError,
    AIProviderError,
    ChatGenerationRequest,
    ChatGenerationResult,
)


DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openrouter": "https://openrouter.ai/api/v1",
}


def _build_endpoint(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise AIProviderConfigurationError("OpenAI-compatible chat provider requires AI_CHAT_BASE_URL")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _classify_status(status_code: int, body: str) -> str:
    lowered = body.lower()
    if status_code == 401 or status_code == 403 or "invalid api key" in lowered or "unauthorized" in lowered:
        return "invalid_api_key"
    if status_code == 408 or "timeout" in lowered or "deadline" in lowered:
        return "provider_timeout"
    if status_code == 429 or "quota" in lowered or "rate limit" in lowered:
        return "quota"
    if status_code >= 500:
        return "transient_network_error"
    if status_code == 400 or "invalid" in lowered:
        return "invalid_session_or_context"
    return "unknown_provider_error"


def _error_message_from_body(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body.strip() or "provider request failed"
    error_payload = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error_payload, dict) and error_payload.get("message"):
        return str(error_payload["message"])
    if isinstance(error_payload, str):
        return error_payload
    return body.strip() or "provider request failed"


class OpenAICompatibleChatProvider:
    def __init__(
        self,
        *,
        provider_name: str,
        api_key: str,
        base_url: str,
        timeout_seconds: int = 30,
    ) -> None:
        if not api_key:
            raise AIProviderConfigurationError(f"{provider_name} chat provider requires AI_CHAT_API_KEY")
        self.provider_name = provider_name
        self.endpoint = _build_endpoint(base_url)
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def generate(self, request: ChatGenerationRequest) -> ChatGenerationResult:
        payload: dict[str, object] = {
            "model": request.model,
            "messages": self._build_messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        if request.response_mime_type == "application/json":
            payload["response_format"] = {"type": "json_object"}

        req = urllib_request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AIProviderError(
                f"{self.provider_name} provider request failed: {_error_message_from_body(body)}",
                error_type=_classify_status(exc.code, body),
                status_code=exc.code,
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise AIProviderError(
                f"{self.provider_name} provider request timed out",
                error_type="provider_timeout",
            ) from exc
        except error.URLError as exc:
            raise AIProviderError(
                f"{self.provider_name} provider network error: {exc}",
                error_type="transient_network_error",
            ) from exc

        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                f"{self.provider_name} provider returned invalid JSON",
                error_type="unknown_provider_error",
            ) from exc

        if not isinstance(parsed, dict):
            raise AIProviderError(
                f"{self.provider_name} provider returned an unexpected payload",
                error_type="unknown_provider_error",
            )
        return ChatGenerationResult(
            text=self._extract_text(parsed),
            usage_metadata=self._extract_usage(parsed),
            raw_response=parsed,
        )

    def _build_messages(self, request: ChatGenerationRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})
        for message in request.messages:
            normalized_role = message.role if message.role in {"system", "user", "assistant"} else "user"
            normalized_content = message.content.strip()
            if normalized_content:
                messages.append({"role": normalized_role, "content": normalized_content})
        messages.append({"role": "user", "content": request.contents})
        return messages

    def _extract_text(self, payload: dict[str, object]) -> str | None:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return None
        message = first_choice.get("message")
        if isinstance(message, dict) and message.get("content") is not None:
            return str(message["content"])
        if first_choice.get("text") is not None:
            return str(first_choice["text"])
        return None

    def _extract_usage(self, payload: dict[str, object]) -> dict[str, int | str | None] | None:
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return None
        result: dict[str, int | str | None] = {}
        for source_name, target_name in (
            ("prompt_tokens", "prompt_token_count"),
            ("completion_tokens", "candidates_token_count"),
            ("total_tokens", "total_token_count"),
        ):
            value = usage.get(source_name)
            if value is not None:
                result[target_name] = int(value)
                result[source_name] = int(value)
        return result or None
