-- Use cosine distance for semantic similarity. Keep vector indexes separate so they can
-- be tuned or rebuilt independently from the base schema.
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_embedding_hnsw
    ON ai_knowledge_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
