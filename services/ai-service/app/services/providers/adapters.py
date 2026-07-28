from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from math import sqrt
from typing import Any

from google import genai
from google.genai import errors as genai_errors, types as genai_types

from app.core.config import settings
from app.services.providers.types import (
    ChatAdapter,
    EmbeddingAdapter,
    EmbeddingRequest,
    ProviderEmbeddingResult,
    ProviderInvocationError,
    ProviderQuotaError,
    ProviderTextResult,
    ProviderUsage,
    TextGenerationRequest,
)


def classify_provider_error(
    exc: Exception | None = None,
    *,
    status_code: int | None = None,
    error_code: str | None = None,
) -> str:
    code = (error_code or "").strip().lower().replace("-", "_").replace(" ", "_")
    message = str(exc or "").lower()
    if status_code in {402, 429} or code in {
        "billing_not_active",
        "insufficient_quota",
        "payment_required",
        "quota_exceeded",
        "rate_limit_exceeded",
        "resource_exhausted",
        "token_limit_exceeded",
    } or re.search(r"\b(?:quota|rate[_ -]?limit(?:ed)?)\b", message):
        return "quota"
    if status_code in {408, 504} or code in {"deadline_exceeded", "request_timeout", "timeout"} or any(
        marker in message for marker in ("timeout", "timed out", "deadline")
    ):
        return "provider_timeout"
    if status_code in {401, 403} or code in {
        "authentication_error",
        "authentication",
        "invalid_api_key",
        "permission_denied",
        "unauthorized",
    } or any(marker in message for marker in ("unauthorized", "forbidden", "invalid api key")):
        return "provider_authentication_error"
    if status_code in {500, 502, 503, 529} or code in {
        "overloaded",
        "provider_overloaded",
        "provider_unavailable",
        "server_error",
        "server",
        "service_unavailable",
    } or any(marker in message for marker in ("unavailable", "connection", "network")):
        return "transient_network_error"
    if status_code in {400, 404, 409, 422} or code in {
        "bad_request",
        "invalid_argument",
        "invalid_request",
        "model_not_found",
    } or any(marker in message for marker in ("invalid", "argument")):
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


def _error_payload_details(
    payload: dict[str, Any],
) -> tuple[int | None, str | None, str]:
    error = payload.get("error")
    if isinstance(error, dict):
        raw_code = error.get("code")
        status_code = (
            int(raw_code)
            if isinstance(raw_code, int)
            or (isinstance(raw_code, str) and raw_code.isdigit())
            else None
        )
        metadata = (
            error.get("metadata")
            if isinstance(error.get("metadata"), dict)
            else {}
        )
        code = (
            metadata.get("error_type")
            or error.get("error_type")
            or error.get("type")
            or (raw_code if status_code is None else None)
        )
        message = error.get("message")
        return (
            status_code,
            str(code) if code is not None else None,
            str(message or ""),
        )
    if error is not None:
        return None, None, str(error)
    return None, None, ""


def _raise_for_error_payload(payload: dict[str, Any]) -> None:
    error = payload.get("error")
    if error is None:
        choices = payload.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if isinstance(choice, dict) and choice.get("error") is not None:
                    error = choice["error"]
                    break
    if error is None:
        return
    status_code, error_code, error_message = _error_payload_details(
        {"error": error}
    )
    provider_error_type = classify_provider_error(
        RuntimeError(error_message),
        status_code=status_code,
        error_code=error_code,
    )
    if provider_error_type == "quota":
        raise ProviderQuotaError("AI provider quota is temporarily unavailable.")
    raise ProviderInvocationError(
        "AI provider returned an error response.",
        provider_error_type=provider_error_type,
    )


def _chat_completions_url(base_url: str | None) -> str:
    normalized = (base_url or "").rstrip("/")
    if not normalized:
        raise ProviderInvocationError("Provider base URL is not configured.", provider_error_type="invalid_request")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _embeddings_url(base_url: str | None) -> str:
    normalized = (base_url or "").rstrip("/")
    if not normalized:
        raise ProviderInvocationError("Provider base URL is not configured.", provider_error_type="invalid_request")
    if normalized.endswith("/embeddings"):
        return normalized
    return f"{normalized}/embeddings"


def _normalize_vector(values: Any, *, expected_dimension: int) -> list[float]:
    if not isinstance(values, list) or len(values) != expected_dimension:
        actual_dimension = len(values) if isinstance(values, list) else 0
        raise ProviderInvocationError(
            f"Embedding dimension mismatch: expected {expected_dimension}, got {actual_dimension}.",
            provider_error_type="invalid_provider_response",
        )
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ProviderInvocationError(
            "Embedding provider returned non-numeric values.",
            provider_error_type="invalid_provider_response",
        )
    vector = [float(value) for value in values]
    magnitude = sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        raise ProviderInvocationError(
            "Embedding provider returned a zero vector.",
            provider_error_type="invalid_provider_response",
        )
    return [value / magnitude for value in vector]


class GeminiChatAdapter:
    def generate_text(self, request: TextGenerationRequest) -> ProviderTextResult:
        try:
            client = genai.Client(api_key=request.api_key)
            response = client.models.generate_content(
                model=request.model_name,
                contents=request.prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=request.system_instruction,
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


class GeminiEmbeddingAdapter:
    def embed(self, request: EmbeddingRequest) -> ProviderEmbeddingResult:
        config_kwargs: dict[str, Any] = {
            "output_dimensionality": request.output_dimension,
        }
        normalized_title = (request.title or "").strip()
        if request.task_type == "RETRIEVAL_QUERY":
            contents = f"task: search result | query: {request.text}"
        elif request.task_type == "RETRIEVAL_DOCUMENT":
            contents = (
                f"title: {normalized_title or 'none'} | text: {request.text}"
            )
        else:
            contents = request.text
        try:
            client = genai.Client(api_key=request.api_key)
            response = client.models.embed_content(
                model=request.model_name,
                contents=contents,
                config=genai_types.EmbedContentConfig(**config_kwargs),
            )
        except genai_errors.ClientError as exc:
            provider_error_type = classify_provider_error(exc)
            if provider_error_type == "quota":
                raise ProviderQuotaError("AI provider quota is temporarily unavailable.") from exc
            raise ProviderInvocationError(
                "AI provider rejected the embedding request.",
                provider_error_type=provider_error_type,
            ) from exc
        except Exception as exc:
            provider_error_type = classify_provider_error(exc)
            if provider_error_type == "quota":
                raise ProviderQuotaError("AI provider quota is temporarily unavailable.") from exc
            raise ProviderInvocationError(
                "AI embedding provider is temporarily unavailable.",
                provider_error_type=provider_error_type,
            ) from exc

        embeddings = getattr(response, "embeddings", None)
        if not isinstance(embeddings, list) or not embeddings:
            raise ProviderInvocationError(
                "Embedding provider returned no embeddings.",
                provider_error_type="invalid_provider_response",
            )
        vector = _normalize_vector(
            getattr(embeddings[0], "values", None),
            expected_dimension=request.output_dimension,
        )
        usage_metadata = getattr(response, "usage_metadata", None)
        usage = ProviderUsage(
            prompt_tokens=_usage_value(usage_metadata, "prompt_token_count", "input_tokens"),
            total_tokens=_usage_value(usage_metadata, "total_token_count", "total_tokens"),
        )
        return ProviderEmbeddingResult(
            vector=vector,
            usage=usage,
            request_json={
                "provider": request.provider_key,
                "model": request.model_name,
                "taskType": request.task_type,
                "outputDimension": request.output_dimension,
                "textLength": len(request.text),
            },
            response_json={
                "provider": request.provider_key,
                "model": request.model_name,
                "embeddingCount": len(embeddings),
                "embeddingDimension": len(vector),
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
        thinking_disabled = request.provider_key == "glm"
        if thinking_disabled:
            payload["thinking"] = {"type": "disabled"}
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}
            if request.require_parameter_support:
                payload["provider"] = {"require_parameters": True}

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
            provider_error_type = classify_provider_error(
                RuntimeError(str(exc.reason)),
                status_code=exc.code,
            )
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

        _raise_for_error_payload(response_json)
        choices = response_json.get("choices")
        first_choice = choices[0] if isinstance(choices, list) and choices else {}
        message = first_choice.get("message") if isinstance(first_choice, dict) else {}
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise ProviderInvocationError(
                "AI provider returned an invalid chat response.",
                provider_error_type="invalid_provider_response",
            )
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
                "thinkingDisabled": thinking_disabled,
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


class OpenAICompatibleEmbeddingAdapter:
    def embed(self, request: EmbeddingRequest) -> ProviderEmbeddingResult:
        payload: dict[str, Any] = {
            "model": request.model_name,
            "input": request.text,
            "dimensions": request.output_dimension,
        }
        http_request = urllib.request.Request(
            _embeddings_url(request.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {request.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "AI Study Platform",
            },
            method="POST",
        )
        timeout = getattr(settings, "ai_embedding_timeout_seconds", settings.ai_chat_timeout_seconds)
        try:
            with urllib.request.urlopen(http_request, timeout=timeout) as response:
                response_json = _safe_json_loads(response.read())
        except urllib.error.HTTPError as exc:
            provider_error_type = classify_provider_error(
                RuntimeError(str(exc.reason)),
                status_code=exc.code,
            )
            if provider_error_type == "quota":
                raise ProviderQuotaError("AI provider quota is temporarily unavailable.") from exc
            raise ProviderInvocationError(
                f"AI embedding provider rejected the request with HTTP {exc.code} ({provider_error_type}).",
                provider_error_type=provider_error_type,
            ) from exc
        except Exception as exc:
            provider_error_type = classify_provider_error(exc)
            if provider_error_type == "quota":
                raise ProviderQuotaError("AI provider quota is temporarily unavailable.") from exc
            raise ProviderInvocationError(
                "AI embedding provider is temporarily unavailable.",
                provider_error_type=provider_error_type,
            ) from exc

        _raise_for_error_payload(response_json)
        data = response_json.get("data")
        first_embedding = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
        vector = _normalize_vector(
            first_embedding.get("embedding"),
            expected_dimension=request.output_dimension,
        )
        usage_json = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
        usage = ProviderUsage(
            prompt_tokens=_usage_value(usage_json, "prompt_tokens", "input_tokens"),
            total_tokens=_usage_value(usage_json, "total_tokens"),
        )
        return ProviderEmbeddingResult(
            vector=vector,
            usage=usage,
            request_json={
                "provider": request.provider_key,
                "model": request.model_name,
                "taskType": request.task_type,
                "outputDimension": request.output_dimension,
                "textLength": len(request.text),
            },
            response_json={
                "provider": request.provider_key,
                "model": request.model_name,
                "embeddingCount": len(data) if isinstance(data, list) else 0,
                "embeddingDimension": len(vector),
                "usage": {
                    "promptTokens": usage.prompt_tokens,
                    "totalTokens": usage.total_tokens,
                },
            },
        )


def build_chat_adapter(adapter_type: str) -> ChatAdapter:
    if adapter_type == "gemini":
        return GeminiChatAdapter()
    if adapter_type == "openai_compatible":
        return OpenAICompatibleChatAdapter()
    raise ProviderInvocationError("AI chat adapter is not implemented.", provider_error_type="provider_not_implemented")


def build_embedding_adapter(adapter_type: str) -> EmbeddingAdapter:
    if adapter_type == "gemini":
        return GeminiEmbeddingAdapter()
    if adapter_type == "openai_compatible":
        return OpenAICompatibleEmbeddingAdapter()
    raise ProviderInvocationError(
        "AI embedding adapter is not implemented.",
        provider_error_type="provider_not_implemented",
    )
