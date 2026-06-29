from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ChatGenerationMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatGenerationRequest:
    model: str
    system_instruction: str | None
    contents: str
    temperature: float
    max_output_tokens: int
    response_mime_type: str | None = None
    messages: tuple[ChatGenerationMessage, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ChatGenerationResult:
    text: str | None
    usage_metadata: dict[str, int | str | None] | None
    raw_response: dict[str, object] | None = None


class ChatProvider(Protocol):
    provider_name: str

    def generate(self, request: ChatGenerationRequest) -> ChatGenerationResult:
        ...


class AIProviderConfigurationError(RuntimeError):
    """Raised when the selected AI provider is unsupported or not configured."""


class AIProviderError(RuntimeError):
    """Raised when the upstream AI provider fails with a classified error type."""

    def __init__(self, message: str, *, error_type: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
