from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.services.indexing.text_chunking_service import TextChunkingService


def test_chunk_text_trims_boundaries_and_hashes_chunks(monkeypatch) -> None:
    # Tests text chunking trims input, overlaps chunks, and hashes content.
    monkeypatch.setattr(
        "app.services.indexing.text_chunking_service.settings",
        SimpleNamespace(ai_chunk_size_chars=6, ai_chunk_overlap_chars=2),
    )

    chunks = TextChunkingService().chunk_text(content_text="  abcdefghij  ")

    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert [chunk.chunk_text for chunk in chunks] == ["abcdef", "efghij"]
    assert [(chunk.start_char, chunk.end_char) for chunk in chunks] == [(0, 6), (4, 10)]
    assert chunks[0].chunk_hash == sha256(b"abcdef").hexdigest()


@pytest.mark.parametrize(
    ("chunk_size", "overlap", "message"),
    [
        (0, 0, "AI_CHUNK_SIZE_CHARS must be greater than 0"),
        (5, -1, "AI_CHUNK_OVERLAP_CHARS must be between 0 and chunk size - 1"),
        (5, 5, "AI_CHUNK_OVERLAP_CHARS must be between 0 and chunk size - 1"),
    ],
)
def test_chunk_text_rejects_invalid_settings(monkeypatch, chunk_size, overlap, message) -> None:
    # Tests invalid chunk size and overlap settings are rejected.
    monkeypatch.setattr(
        "app.services.indexing.text_chunking_service.settings",
        SimpleNamespace(ai_chunk_size_chars=chunk_size, ai_chunk_overlap_chars=overlap),
    )

    with pytest.raises(Exception) as exc_info:
        TextChunkingService().chunk_text(content_text="content")

    assert message in str(exc_info.value)


def test_chunk_text_rejects_blank_content() -> None:
    # Tests blank content cannot be chunked.
    with pytest.raises(Exception) as exc_info:
        TextChunkingService().chunk_text(content_text="   ")

    assert "content_text is required for chunking" in str(exc_info.value)
