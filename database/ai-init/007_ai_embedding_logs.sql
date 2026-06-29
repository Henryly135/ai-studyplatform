CREATE TABLE IF NOT EXISTS ai_embedding_logs (
    embedding_log_id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NULL,
    user_id BIGINT NOT NULL,
    course_id BIGINT NULL,
    module_id BIGINT NULL,
    material_id BIGINT NULL,
    chunk_index INTEGER NULL,
    chunk_hash VARCHAR(64) NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(100) NULL,
    task_type VARCHAR(50) NULL,
    title VARCHAR(255) NULL,
    input_text TEXT NOT NULL,
    input_chars INTEGER NOT NULL,
    provider_input_tokens INTEGER NULL,
    provider_total_tokens INTEGER NULL,
    vector_length INTEGER NULL,
    output_dimensionality INTEGER NULL,
    request_json JSONB NULL,
    response_json JSONB NULL,
    latency_ms INTEGER NULL,
    status ai_prompt_status NOT NULL,
    error_message TEXT NULL,
    trace_id VARCHAR(100) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_embedding_logs_job
        FOREIGN KEY (job_id) REFERENCES ai_index_jobs (job_id) ON DELETE SET NULL
);

COMMENT ON TABLE ai_embedding_logs IS 'Audits embedding calls, vector generation, and token usage for indexing and retrieval pipelines.';

CREATE INDEX IF NOT EXISTS idx_ai_embedding_logs_job_id
    ON ai_embedding_logs (job_id);

CREATE INDEX IF NOT EXISTS idx_ai_embedding_logs_material_id
    ON ai_embedding_logs (material_id);

CREATE INDEX IF NOT EXISTS idx_ai_embedding_logs_created_at
    ON ai_embedding_logs (created_at DESC);
