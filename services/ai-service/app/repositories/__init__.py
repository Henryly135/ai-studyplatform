"""Repository layer for the AI service."""

from app.repositories.ai_embedding_logs_repository import AIEmbeddingLogsRepository
from app.repositories.ai_chat_messages_repository import AIChatMessagesRepository
from app.repositories.ai_chat_sessions_repository import AIChatSessionsRepository
from app.repositories.ai_index_jobs_repository import AIIndexJobsRepository
from app.repositories.ai_knowledge_chunks_repository import AIKnowledgeChunksRepository
from app.repositories.ai_knowledge_sources_repository import AIKnowledgeSourcesRepository
from app.repositories.ai_model_catalog_repository import AIModelCatalogRepository
from app.repositories.ai_prompt_logs_repository import AIPromptLogsRepository
from app.repositories.ai_retrieval_logs_repository import AIRetrievalLogsRepository
from app.repositories.learner_global_profile_assets_repository import LearnerGlobalProfileAssetsRepository
from app.repositories.learner_module_profile_assets_repository import LearnerModuleProfileAssetsRepository

__all__ = [
    "AIEmbeddingLogsRepository",
    "AIChatSessionsRepository",
    "AIChatMessagesRepository",
    "AIIndexJobsRepository",
    "AIKnowledgeSourcesRepository",
    "AIKnowledgeChunksRepository",
    "AIModelCatalogRepository",
    "AIPromptLogsRepository",
    "AIRetrievalLogsRepository",
    "LearnerGlobalProfileAssetsRepository",
    "LearnerModuleProfileAssetsRepository",
]
