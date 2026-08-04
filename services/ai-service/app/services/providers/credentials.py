from __future__ import annotations

import base64
import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.ai_model_catalog_repository import AIModelCatalogRepository
from app.services.providers.model_registry import PROVIDER_DEFINITION_BY_KEY
from app.services.providers.types import ProviderConfigurationError, ProviderCredentials

_SECRET_PATTERNS = (
    re.compile(r"(api[_-]?key=)[^,\s}]+", re.IGNORECASE),
    re.compile(r"(authorization['\"]?\s*:\s*['\"]?bearer\s+)[^,'\"\s}]+", re.IGNORECASE),
    re.compile(r"(bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
)


def redact_secret_text(value: object) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


def api_key_hint(api_key: str) -> str:
    normalized = api_key.strip()
    if len(normalized) <= 4:
        return "****"
    return f"****{normalized[-4:]}"


class ProviderCredentialCipher:
    def __init__(self, secret: str | None = None) -> None:
        self.secret = (secret if secret is not None else settings.ai_provider_key_encryption_secret).strip()

    def _fernet(self) -> Fernet:
        if not self.secret:
            raise ProviderConfigurationError("AI provider key encryption secret is not configured.")
        key = base64.urlsafe_b64encode(hashlib.sha256(self.secret.encode("utf-8")).digest())
        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        normalized = plaintext.strip()
        if not normalized:
            raise ProviderConfigurationError("API key is required.")
        return self._fernet().encrypt(normalized.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ProviderConfigurationError("Stored AI provider credential cannot be decrypted.") from exc


class ProviderCredentialService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = AIModelCatalogRepository(session)
        self.cipher = ProviderCredentialCipher()

    def get_credentials_for_provider(self, provider_key: str) -> ProviderCredentials:
        definition = self._require_supported_provider(provider_key)
        provider = self.repo.get_provider(provider_key)

        credential = self.repo.get_credential(provider_key)
        if credential is None or not credential.is_enabled or not credential.encrypted_api_key:
            raise ProviderConfigurationError("AI provider API key is not configured.")

        api_key = self.cipher.decrypt(credential.encrypted_api_key)
        default_base_url = provider.default_base_url if provider is not None else definition.default_base_url if definition else None
        return ProviderCredentials(
            provider_key=provider_key,
            api_key=api_key,
            base_url=credential.base_url_override or default_base_url,
        )

    def save_credentials(
        self,
        *,
        provider_key: str,
        api_key: str,
        base_url_override: str | None,
        is_enabled: bool,
    ):
        self._require_supported_provider(provider_key)
        provider = self.repo.get_provider(provider_key)
        if provider is None:
            raise ProviderConfigurationError("AI provider is not supported.")
        if not provider.backend_supported:
            raise ProviderConfigurationError("AI provider is display-only in this release.")
        encrypted = self.cipher.encrypt(api_key)
        credential = self.repo.upsert_credential(
            provider_key=provider_key,
            encrypted_api_key=encrypted,
            api_key_hint=api_key_hint(api_key),
            base_url_override=base_url_override.strip() if base_url_override and base_url_override.strip() else None,
            is_enabled=is_enabled,
        )
        self.session.commit()
        self.session.refresh(credential)
        return credential

    def delete_credentials(self, *, provider_key: str) -> bool:
        self._require_supported_provider(provider_key)
        deleted = self.repo.delete_credential(provider_key)
        self.session.commit()
        return deleted

    @staticmethod
    def _require_supported_provider(provider_key: str):
        definition = PROVIDER_DEFINITION_BY_KEY.get(provider_key)
        if definition is None:
            raise ProviderConfigurationError("AI provider is not supported.")
        if not definition.backend_supported:
            raise ProviderConfigurationError(
                "AI provider is display-only in this release."
            )
        return definition
