-- Canonical chunks are provider-independent. The legacy single-vector columns
-- remain available (nullable) for rollback while all new reads use this table.
ALTER TABLE ai_knowledge_chunks
    ALTER COLUMN embedding_model DROP NOT NULL,
    ALTER COLUMN embedding DROP NOT NULL;

CREATE TABLE IF NOT EXISTS ai_knowledge_chunk_embeddings (
    chunk_embedding_id BIGSERIAL PRIMARY KEY,
    chunk_id BIGINT NOT NULL
        REFERENCES ai_knowledge_chunks(chunk_id) ON DELETE CASCADE,
    embedding_model_id VARCHAR(120) NOT NULL
        REFERENCES ai_model_catalog(model_id) ON DELETE CASCADE,
    embedding_version VARCHAR(160) NOT NULL,
    embedding_dimension INTEGER NOT NULL DEFAULT 1024,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ai_chunk_embeddings_chunk_model
        UNIQUE (chunk_id, embedding_model_id),
    CONSTRAINT ck_ai_chunk_embeddings_dimension
        CHECK (embedding_dimension = 1024)
);

CREATE TABLE IF NOT EXISTS ai_knowledge_source_embedding_statuses (
    source_id BIGINT NOT NULL
        REFERENCES ai_knowledge_sources(source_id) ON DELETE CASCADE,
    embedding_model_id VARCHAR(120) NOT NULL
        REFERENCES ai_model_catalog(model_id) ON DELETE CASCADE,
    embedding_version VARCHAR(160) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    expected_chunk_count INTEGER NOT NULL DEFAULT 0,
    indexed_chunk_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NULL,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_id, embedding_model_id),
    CONSTRAINT ck_ai_source_embedding_status
        CHECK (status IN ('queued', 'running', 'success', 'failed')),
    CONSTRAINT ck_ai_source_embedding_chunk_counts
        CHECK (
            expected_chunk_count >= 0
            AND indexed_chunk_count >= 0
            AND indexed_chunk_count <= expected_chunk_count
        )
);

CREATE INDEX IF NOT EXISTS idx_ai_chunk_embeddings_model_id
    ON ai_knowledge_chunk_embeddings (embedding_model_id);
CREATE INDEX IF NOT EXISTS idx_ai_source_embedding_status_model_status
    ON ai_knowledge_source_embedding_statuses (embedding_model_id, status);
DROP INDEX IF EXISTS idx_ai_chunk_embeddings_vector_hnsw;
DROP INDEX IF EXISTS idx_ai_chunk_embeddings_gemini_hnsw;
DROP INDEX IF EXISTS idx_ai_chunk_embeddings_glm_hnsw;
DROP INDEX IF EXISTS idx_ai_chunk_embeddings_openrouter_hnsw;

-- The first multi-provider release deliberately uses exact cosine ordering
-- after model/course filters. A shared HNSW graph would mix incompatible
-- provider spaces, while ANN post-filtering can miss top-k course results.

CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_rag_scope
    ON ai_knowledge_chunks (course_id, module_id, publish_status, is_active);

COMMENT ON TABLE ai_knowledge_chunk_embeddings IS
    'Stores one 1024-dimensional vector per canonical chunk and embedding model.';
COMMENT ON TABLE ai_knowledge_source_embedding_statuses IS
    'Tracks per-source coverage and failures for each configured embedding model.';
