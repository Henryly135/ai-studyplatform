"""Service layer for the AI service."""

from app.services.chat.ai_chat_service import (
    AIChatConfigurationError,
    AIChatQuotaError,
    AIChatSessionError,
    generate_chat_reply,
    persist_chat,
)
from app.services.indexing.knowledge_indexing_service import (
    KnowledgeIndexingResult,
    KnowledgeIndexingService,
    SourceUpsert,
)
from app.services.indexing.embedding_service import EmbeddingResult, EmbeddingService
from app.services.indexing.material_content_service import (
    ExtractedMaterialContent,
    MaterialContentRequest,
    MaterialContentService,
)
from app.services.indexing.text_chunking_service import TextChunk, TextChunkingService

__all__ = [
    "AIChatConfigurationError",
    "AIChatQuotaError",
    "AIChatSessionError",
    "generate_chat_reply",
    "KnowledgeIndexingResult",
    "KnowledgeIndexingService",
    "EmbeddingResult",
    "EmbeddingService",
    "ExtractedMaterialContent",
    "MaterialContentRequest",
    "MaterialContentService",
    "SourceUpsert",
    "TextChunk",
    "TextChunkingService",
    "persist_chat",
]
