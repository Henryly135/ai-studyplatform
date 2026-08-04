from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ModelProviderDefinition:
    provider_key: str
    display_name: str
    adapter_type: str
    default_base_url: str | None
    backend_supported: bool
    display_order: int
    require_json_parameter_support: bool = False


@dataclass(frozen=True)
class ModelDefinition:
    model_id: str
    provider_key: str
    model_name: str
    display_name: str
    backend_supported: bool
    display_only: bool
    supports_chat: bool
    supports_json: bool
    supports_embedding: bool
    supports_rag_answer: bool
    supports_rag_indexing: bool
    embedding_dimension: int | None = None
    display_order: int = 100
    unavailable_reason: str | None = None
    paired_embedding_model_id: str | None = None


@dataclass(frozen=True)
class ProviderCredentials:
    provider_key: str
    api_key: str
    base_url: str | None


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ProviderTextResult:
    text: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    request_json: dict | None = None
    response_json: dict | None = None


@dataclass(frozen=True)
class TextGenerationRequest:
    provider_key: str
    model_name: str
    api_key: str
    base_url: str | None
    prompt: str
    system_instruction: str | None = None
    temperature: float = 0.5
    max_output_tokens: int = 900
    json_mode: bool = False
    require_parameter_support: bool = False


@dataclass(frozen=True)
class EmbeddingRequest:
    provider_key: str
    model_name: str
    api_key: str
    base_url: str | None
    text: str
    output_dimension: int
    task_type: str = "RETRIEVAL_DOCUMENT"
    title: str | None = None


@dataclass(frozen=True)
class ProviderEmbeddingResult:
    vector: list[float]
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    request_json: dict | None = None
    response_json: dict | None = None


class ChatAdapter(Protocol):
    def generate_text(self, request: TextGenerationRequest) -> ProviderTextResult: ...


class EmbeddingAdapter(Protocol):
    def embed(self, request: EmbeddingRequest) -> ProviderEmbeddingResult: ...


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider cannot be used because credentials or config are missing."""


class ProviderQuotaError(RuntimeError):
    """Raised when a provider rejects a request because of quota or rate limits."""


class ProviderInvocationError(RuntimeError):
    """Raised for sanitized upstream model provider failures."""

    def __init__(self, message: str, *, provider_error_type: str = "unknown_provider_error") -> None:
        super().__init__(message)
        self.provider_error_type = provider_error_type
