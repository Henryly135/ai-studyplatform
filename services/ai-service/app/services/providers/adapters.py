from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from google import genai
from google.genai import errors as genai_errors, types as genai_types

from app.core.config import settings
from app.services.providers.types import (
    ProviderInvocationError,
    ProviderQuotaError,
    ProviderTextResult,
    ProviderUsage,
    TextGenerationRequest,
)


def classify_provider_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "resource_exhausted" in message or "quota" in message or "rate" in message or "429" in message:
        return "quota"
    if "timeout" in message or "timed out" in message or "deadline" in message:
        return "provider_timeout"
    if "401" in message or "403" in message or "unauthorized" in message or "forbidden" in message:
        return "provider_authentication_error"
    if "503" in message or "unavailable" in message or "connection" in message or "network" in message:
        return "transient_network_error"
    if "invalid" in message or "400" in message or "argument" in message:
        return "invalid_request"
    return "unknown_provider_error"


def _usage_value(data: Any, *names: str) -> int | None:
    for name in names:
        if isinstance(data, dict) and data.get(name) is not None:
            return int(data[name])
        value = getattr(data, name, None)
        if value is not None:
            return int(value)
    return None


def _safe_json_loads(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _chat_completions_url(base_url: str | None) -> str:
    normalized = (base_url or "").rstrip("/")
    if not normalized:
        raise ProviderInvocationError("Provider base URL is not configured.", provider_error_type="invalid_request")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


class GeminiChatAdapter:
    def generate_text(self, request: TextGenerationRequest) -> ProviderTextResult:
        try:
            client = genai.Client(api_key=request.api_key)
            response = client.models.generate_content(
                model=request.model_name,
                contents=request.prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=request.system_instruction,
                    temperature=request.temperature,
                    max_output_tokens=request.max_output_tokens,
                    response_mime_type="application/json" if request.json_mode else None,
                ),
            )
        except genai_errors.ClientError as exc:
            provider_error_type = classify_provider_error(exc)
            if provider_error_type == "quota":
                raise ProviderQuotaError("AI provider quota is temporarily unavailable.") from exc
            raise ProviderInvocationError(
                "AI provider rejected the request.",
                provider_error_type=provider_error_type,
            ) from exc
        except Exception as exc:
            provider_error_type = classify_provider_error(exc)
            if provider_error_type == "quota":
                raise ProviderQuotaError("AI provider quota is temporarily unavailable.") from exc
            raise ProviderInvocationError(
                "AI provider is temporarily unavailable.",
                provider_error_type=provider_error_type,
            ) from exc

        usage_metadata = getattr(response, "usage_metadata", None)
        usage = ProviderUsage(
            prompt_tokens=_usage_value(usage_metadata, "prompt_token_count", "input_tokens"),
            completion_tokens=_usage_value(usage_metadata, "candidates_token_count", "output_tokens"),
            total_tokens=_usage_value(usage_metadata, "total_token_count", "total_tokens"),
        )
        return ProviderTextResult(
            text=(getattr(response, "text", None) or "").strip(),
            usage=usage,
            request_json={
                "provider": request.provider_key,
                "model": request.model_name,
                "jsonMode": request.json_mode,
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
            },
            response_json={
                "provider": request.provider_key,
                "model": request.model_name,
                "textLength": len(getattr(response, "text", None) or ""),
                "usage": {
                    "promptTokens": usage.prompt_tokens,
                    "completionTokens": usage.completion_tokens,
                    "totalTokens": usage.total_tokens,
                },
            },
        )


class OpenAICompatibleChatAdapter:
    def generate_text(self, request: TextGenerationRequest) -> ProviderTextResult:
        payload: dict[str, Any] = {
            "model": request.model_name,
            "messages": [
                *(
                    [{"role": "system", "content": request.system_instruction}]
                    if request.system_instruction
                    else []
                ),
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        http_request = urllib.request.Request(
            _chat_completions_url(request.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {request.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "AI Study Platform",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=settings.ai_chat_timeout_seconds) as response:
                response_json = _safe_json_loads(response.read())
        except urllib.error.HTTPError as exc:
            provider_error_type = classify_provider_error(RuntimeError(f"{exc.code} {exc.reason}"))
            if provider_error_type == "quota":
                raise ProviderQuotaError("AI provider quota is temporarily unavailable.") from exc
            raise ProviderInvocationError(
                f"AI provider rejected the request with HTTP {exc.code} ({provider_error_type}).",
                provider_error_type=provider_error_type,
            ) from exc
        except Exception as exc:
            provider_error_type = classify_provider_error(exc)
            if provider_error_type == "quota":
                raise ProviderQuotaError("AI provider quota is temporarily unavailable.") from exc
            raise ProviderInvocationError(
                "AI provider is temporarily unavailable.",
                provider_error_type=provider_error_type,
            ) from exc

        choices = response_json.get("choices")
        first_choice = choices[0] if isinstance(choices, list) and choices else {}
        message = first_choice.get("message") if isinstance(first_choice, dict) else {}
        text = message.get("content") if isinstance(message, dict) else None
        usage_json = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
        usage = ProviderUsage(
            prompt_tokens=_usage_value(usage_json, "prompt_tokens", "input_tokens"),
            completion_tokens=_usage_value(usage_json, "completion_tokens", "output_tokens"),
            total_tokens=_usage_value(usage_json, "total_tokens"),
        )
        return ProviderTextResult(
            text=(text or "").strip(),
            usage=usage,
            request_json={
                "provider": request.provider_key,
                "model": request.model_name,
                "jsonMode": request.json_mode,
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
            },
            response_json={
                "provider": request.provider_key,
                "model": request.model_name,
                "choiceCount": len(choices) if isinstance(choices, list) else 0,
                "finishReason": first_choice.get("finish_reason") if isinstance(first_choice, dict) else None,
                "usage": {
                    "promptTokens": usage.prompt_tokens,
                    "completionTokens": usage.completion_tokens,
                    "totalTokens": usage.total_tokens,
                },
            },
        )


def build_chat_adapter(provider_key: str):
    if provider_key == "gemini":
        return GeminiChatAdapter()
    if provider_key in {"deepseek", "glm", "openrouter"}:
        return OpenAICompatibleChatAdapter()
    raise ProviderInvocationError("AI provider is not implemented.", provider_error_type="provider_not_implemented")
