from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from app.core.config import settings
from platform_common.errors import invalid_request_error


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    chunk_text: str
    chunk_hash: str
    start_char: int
    end_char: int


class TextChunkingService:
    def chunk_text(self, *, content_text: str) -> list[TextChunk]:
        normalized = content_text.strip()
        if not normalized:
            raise invalid_request_error("content_text is required for chunking")

        chunk_size = settings.ai_chunk_size_chars
        overlap = settings.ai_chunk_overlap_chars
        if chunk_size <= 0:
            raise invalid_request_error("AI_CHUNK_SIZE_CHARS must be greater than 0")
        if overlap < 0 or overlap >= chunk_size:
            raise invalid_request_error("AI_CHUNK_OVERLAP_CHARS must be between 0 and chunk size - 1")

        step = chunk_size - overlap
        chunks: list[TextChunk] = []
        index = 0

        for start in range(0, len(normalized), step):
            end = min(start + chunk_size, len(normalized))
            raw_chunk = normalized[start:end]
            chunk_text = raw_chunk.strip()
            if not chunk_text:
                continue

            leading_offset = len(raw_chunk) - len(raw_chunk.lstrip())
            trailing_offset = len(raw_chunk.rstrip())
            actual_start = start + leading_offset
            actual_end = start + trailing_offset

            chunks.append(
                TextChunk(
                    chunk_index=index,
                    chunk_text=chunk_text,
                    chunk_hash=sha256(chunk_text.encode("utf-8")).hexdigest(),
                    start_char=actual_start,
                    end_char=actual_end,
                )
            )
            index += 1

            if end >= len(normalized):
                break

        if not chunks:
            raise invalid_request_error("Unable to create text chunks from extracted content")
        return chunks
