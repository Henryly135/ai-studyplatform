from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.indexing.material_content_service import MaterialContentRequest, MaterialContentService


def test_extract_text_reads_local_text_file(tmp_path) -> None:
    # Tests local markdown files are read and trimmed into extracted content.
    material_path = tmp_path / "lesson.md"
    material_path.write_text("  # Lesson\n\ncontent  ", encoding="utf-8")

    result = MaterialContentService().extract_text(
        request=MaterialContentRequest(
            title="Lesson",
            content_type="text/markdown",
            storage_provider="LOCAL",
            absolute_path=str(material_path),
            storage_bucket=None,
            object_key="lesson.md",
        )
    )

    assert result.storage_provider == "local"
    assert result.content_text == "# Lesson\n\ncontent"


def test_extract_text_rejects_unsupported_provider() -> None:
    # Tests unsupported material storage providers are rejected.
    with pytest.raises(Exception) as exc_info:
        MaterialContentService().extract_text(
            request=MaterialContentRequest(
                title="Lesson",
                content_type="text/plain",
                storage_provider="s3",
                absolute_path=None,
                storage_bucket=None,
                object_key="lesson.txt",
            )
        )

    assert "Unsupported storageProvider 's3'" in str(exc_info.value)


def test_read_minio_bytes_closes_response(monkeypatch) -> None:
    # Tests MinIO response objects are closed and released after reading.
    response = SimpleNamespace(
        closed=False,
        released=False,
        read=lambda: b"content",
        close=lambda: setattr(response, "closed", True),
        release_conn=lambda: setattr(response, "released", True),
    )
    client = SimpleNamespace(get_object=lambda bucket, key: response)
    monkeypatch.setattr("app.services.indexing.material_content_service.build_minio_client", lambda **_: client)

    payload = MaterialContentService()._read_minio_bytes(bucket_name="bucket", object_key="lesson.txt")

    assert payload == b"content"
    assert response.closed is True
    assert response.released is True


def test_decode_text_falls_back_to_latin1() -> None:
    # Tests text decoding falls back to latin-1 when UTF-8 fails.
    assert MaterialContentService()._decode_text(b"caf\xe9") == "caf\xe9"
