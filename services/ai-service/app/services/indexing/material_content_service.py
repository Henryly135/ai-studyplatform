from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.core.config import settings
from platform_common.errors import invalid_request_error
from platform_common.storage import build_minio_client

_TEXT_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "application/json",
    "text/csv",
}
_WORD_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass(frozen=True)
class MaterialContentRequest:
    title: str
    content_type: str | None
    storage_provider: str
    absolute_path: str | None
    storage_bucket: str | None
    object_key: str


@dataclass(frozen=True)
class ExtractedMaterialContent:
    title: str
    content_type: str | None
    storage_provider: str
    object_key: str
    content_text: str


class MaterialContentService:
    def extract_text(self, *, request: MaterialContentRequest) -> ExtractedMaterialContent:
        normalized_provider = request.storage_provider.strip().lower()
        payload = self._read_bytes(request=request, storage_provider=normalized_provider)
        content_text = self._extract_text_payload(
            payload=payload,
            content_type=(request.content_type or "").strip().lower() or None,
            object_key=request.object_key,
        )
        if not content_text.strip():
            raise invalid_request_error("Extracted material content is empty")

        return ExtractedMaterialContent(
            title=request.title,
            content_type=request.content_type,
            storage_provider=normalized_provider,
            object_key=request.object_key,
            content_text=content_text.strip(),
        )

    def _read_bytes(self, *, request: MaterialContentRequest, storage_provider: str) -> bytes:
        if storage_provider == "local":
            return self._read_local_bytes(absolute_path=request.absolute_path)
        if storage_provider == "minio":
            return self._read_minio_bytes(
                bucket_name=request.storage_bucket,
                object_key=request.object_key,
            )
        raise invalid_request_error(f"Unsupported storageProvider '{request.storage_provider}'")

    def _read_local_bytes(self, *, absolute_path: str | None) -> bytes:
        if not absolute_path or not absolute_path.strip():
            raise invalid_request_error("absolutePath is required for local material indexing")
        target_path = Path(absolute_path)
        if not target_path.is_file():
            raise invalid_request_error(f"Material file not found at '{absolute_path}'")
        return target_path.read_bytes()

    def _read_minio_bytes(self, *, bucket_name: str | None, object_key: str) -> bytes:
        if not bucket_name or not bucket_name.strip():
            raise invalid_request_error("storageBucket is required for MinIO material indexing")

        client = build_minio_client(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
        )
        response = client.get_object(bucket_name.strip(), object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def _extract_text_payload(
        self,
        *,
        payload: bytes,
        content_type: str | None,
        object_key: str,
    ) -> str:
        suffix = Path(object_key).suffix.lower()
        if content_type == "application/pdf" or suffix == ".pdf":
            return self._extract_pdf_text(payload)
        if content_type in _WORD_CONTENT_TYPES or suffix == ".docx":
            return self._extract_docx_text(payload)
        if content_type in _TEXT_CONTENT_TYPES or suffix in {".txt", ".md", ".csv", ".json"}:
            return self._decode_text(payload)
        raise invalid_request_error(
            f"Unsupported material content type '{content_type or suffix or 'unknown'}' for text extraction"
        )

    def _extract_pdf_text(self, payload: bytes) -> str:
        reader = PdfReader(BytesIO(payload))
        page_text: list[str] = []
        for page in reader.pages:
            page_text.append((page.extract_text() or "").strip())
        return "\n\n".join(text for text in page_text if text)

    def _extract_docx_text(self, payload: bytes) -> str:
        document = Document(BytesIO(payload))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n\n".join(paragraphs)

    def _decode_text(self, payload: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise invalid_request_error("Unable to decode material text content")
