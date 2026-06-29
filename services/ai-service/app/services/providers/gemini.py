from __future__ import annotations

from google import genai
from google.genai import errors as genai_errors, types

from app.services.providers.types import (
    AIProviderConfigurationError,
    AIProviderError,
    ChatGenerationRequest,
    ChatGenerationResult,
)


def _safe_usage_metadata(usage_metadata: object) -> dict[str, int | str | None] | None:
    if usage_metadata is None:
        return None
    if isinstance(usage_metadata, dict):
        return usage_metadata

    result: dict[str, int | str | None] = {}
    for name in (
        "prompt_token_count",
        "input_tokens",
        "candidates_token_count",
        "output_tokens",
        "total_token_count",
        "total_tokens",
    ):
        value = getattr(usage_metadata, name, None)
        if value is not None:
            result[name] = int(value)
    return result or None


def classify_provider_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "resource_exhausted" in message or "quota" in message or "429" in message:
        return "quota"
    if "api key" in message or "invalid key" in message or "unauthorized" in message or "401" in message:
        return "invalid_api_key"
    if "timeout" in message or "timed out" in message or "deadline" in message:
        return "provider_timeout"
    if (
        "503" in message
        or "unavailable" in message
        or "connection" in message
        or "network" in message
        or "temporary failure" in message
        or "reset by peer" in message
    ):
        return "transient_network_error"
    if "invalid" in message or "context" in message or "400" in message or "argument" in message:
        return "invalid_session_or_context"
    return "unknown_provider_error"


class GeminiChatProvider:
    provider_name = "gemini"

    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise AIProviderConfigurationError("Gemini chat provider requires GEMINI_API_KEY or AI_CHAT_API_KEY")
        self.client = genai.Client(api_key=api_key)

    def generate(self, request: ChatGenerationRequest) -> ChatGenerationResult:
        try:
            response = self.client.models.generate_content(
                model=request.model,
                contents=self._render_contents(request),
                config=types.GenerateContentConfig(
                    system_instruction=request.system_instruction,
                    temperature=request.temperature,
                    max_output_tokens=request.max_output_tokens,
                    response_mime_type=request.response_mime_type,
                ),
            )
        except (genai_errors.ClientError, genai_errors.ServerError) as exc:
            raise AIProviderError(
                f"Gemini provider request failed: {exc}",
                error_type=classify_provider_error(exc),
            ) from exc

        usage_metadata = getattr(response, "usage_metadata", None)
        return ChatGenerationResult(
            text=getattr(response, "text", None),
            usage_metadata=_safe_usage_metadata(usage_metadata),
            raw_response={"text": getattr(response, "text", None), "usage_metadata": _safe_usage_metadata(usage_metadata)},
        )

    def _render_contents(self, request: ChatGenerationRequest) -> str:
        if not request.messages:
            return request.contents

        history = "\n".join(
            f"{message.role}: {message.content.strip()}"
            for message in request.messages
            if message.content.strip()
        )
        if not history:
            return request.contents
        return f"Conversation history:\n{history}\n\nCurrent user message:\n{request.contents}"
