DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_session_status') THEN
        CREATE TYPE ai_session_status AS ENUM ('active', 'archived', 'closed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_message_role') THEN
        CREATE TYPE ai_message_role AS ENUM ('system', 'user', 'assistant', 'tool');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_message_type') THEN
        CREATE TYPE ai_message_type AS ENUM ('plain_text', 'system_notice', 'retrieval_context');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_prompt_call_type') THEN
        CREATE TYPE ai_prompt_call_type AS ENUM ('chat', 'retrieval', 'query_rewrite', 'summarization', 'embedding', 'indexing_system');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_prompt_status') THEN
        CREATE TYPE ai_prompt_status AS ENUM ('success', 'failed', 'timeout');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_job_status') THEN
        CREATE TYPE ai_job_status AS ENUM ('blocked', 'queued', 'running', 'success', 'failed', 'superseded', 'cancelled');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_event_status') THEN
        CREATE TYPE ai_event_status AS ENUM ('processing', 'processed', 'failed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_knowledge_source_type') THEN
        CREATE TYPE ai_knowledge_source_type AS ENUM ('material', 'module_summary', 'course_summary', 'faq');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_visibility_scope') THEN
        CREATE TYPE ai_visibility_scope AS ENUM ('public', 'course_only', 'private');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_publish_status') THEN
        CREATE TYPE ai_publish_status AS ENUM ('draft', 'published', 'archived');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_index_job_type') THEN
        CREATE TYPE ai_index_job_type AS ENUM ('index_material', 'reindex_material', 'delete_material_index', 'reindex_course');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_index_source_type') THEN
        CREATE TYPE ai_index_source_type AS ENUM ('material', 'module', 'course', 'faq');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_feedback_type') THEN
        CREATE TYPE ai_feedback_type AS ENUM ('like', 'dislike', 'report');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_profile_asset_status') THEN
        CREATE TYPE ai_profile_asset_status AS ENUM ('active', 'archived');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS ai_chat_sessions (
    session_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    course_id BIGINT NULL,
    module_id BIGINT NULL,
    session_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NULL,
    status ai_session_status NOT NULL DEFAULT 'active',
    last_message_at TIMESTAMP NULL,
    last_user_message_at TIMESTAMP NULL,
    last_assistant_message_at TIMESTAMP NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    summary_text TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE ai_chat_sessions IS 'Stores AI chat session metadata for user conversations.';

CREATE TABLE IF NOT EXISTS ai_knowledge_sources (
    source_id BIGSERIAL PRIMARY KEY,
    source_type ai_knowledge_source_type NOT NULL,
    source_ref_id VARCHAR(100) NOT NULL,
    course_id BIGINT NULL,
    module_id BIGINT NULL,
    material_id BIGINT NULL,
    title VARCHAR(500) NULL,
    content_text TEXT NOT NULL,
    content_markdown TEXT NULL,
    language_code VARCHAR(20) NULL,
    visibility_scope ai_visibility_scope NOT NULL DEFAULT 'course_only',
    publish_status ai_publish_status NOT NULL DEFAULT 'published',
    content_hash VARCHAR(128) NOT NULL,
    embedding_model VARCHAR(100) NULL,
    embedding_version VARCHAR(50) NULL,
    source_version VARCHAR(500) NULL,
    metadata_json JSONB NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    origin_event_id VARCHAR(100) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ai_knowledge_sources_type_ref UNIQUE (source_type, source_ref_id)
);

COMMENT ON TABLE ai_knowledge_sources IS 'Stores original knowledge records before chunking and embedding.';

CREATE TABLE IF NOT EXISTS ai_index_jobs (
    job_id BIGSERIAL PRIMARY KEY,
    job_type ai_index_job_type NOT NULL,
    source_type ai_index_source_type NOT NULL,
    source_ref_id VARCHAR(100) NOT NULL,
    course_id BIGINT NULL,
    module_id BIGINT NULL,
    material_id BIGINT NULL,
    source_version VARCHAR(500) NULL,
    content_hash VARCHAR(128) NULL,
    status ai_job_status NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 100,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    metadata_json JSONB NULL,
    trigger_event_id VARCHAR(100) NULL,
    worker_id VARCHAR(100) NULL,
    next_retry_at TIMESTAMP NULL,
    locked_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL
);

COMMENT ON TABLE ai_index_jobs IS 'Tracks asynchronous indexing jobs consumed by AI indexing workers.';

CREATE TABLE IF NOT EXISTS ai_consumed_events (
    event_id VARCHAR(100) PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    topic_name VARCHAR(100) NOT NULL,
    partition_id INTEGER NOT NULL,
    offset_value BIGINT NOT NULL,
    status ai_event_status NOT NULL,
    error_message TEXT NULL,
    processed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ai_consumed_events_topic_partition_offset UNIQUE (topic_name, partition_id, offset_value)
);

COMMENT ON TABLE ai_consumed_events IS 'Stores consumed Kafka events for idempotency and replay protection.';

CREATE TABLE IF NOT EXISTS ai_chat_messages (
    message_id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL,
    role ai_message_role NOT NULL,
    message_type ai_message_type NOT NULL DEFAULT 'plain_text',
    parent_message_id BIGINT NULL,
    content_text TEXT NOT NULL,
    is_visible_to_user BOOLEAN NOT NULL DEFAULT TRUE,
    retrieval_trace_json JSONB NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_chat_messages_session
        FOREIGN KEY (session_id) REFERENCES ai_chat_sessions (session_id) ON DELETE CASCADE,
    CONSTRAINT fk_ai_chat_messages_parent
        FOREIGN KEY (parent_message_id) REFERENCES ai_chat_messages (message_id) ON DELETE SET NULL
);

COMMENT ON TABLE ai_chat_messages IS 'Stores message history for AI chat sessions.';

CREATE TABLE IF NOT EXISTS ai_prompt_logs (
    prompt_log_id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NULL,
    message_id BIGINT NULL,
    user_id BIGINT NOT NULL,
    call_type ai_prompt_call_type NOT NULL,
    prompt_template_name VARCHAR(100) NULL,
    model_name VARCHAR(100) NOT NULL,
    input_text TEXT NOT NULL,
    output_text TEXT NULL,
    request_json JSONB NULL,
    response_json JSONB NULL,
    prompt_tokens INTEGER NULL,
    completion_tokens INTEGER NULL,
    total_tokens INTEGER NULL,
    latency_ms INTEGER NULL,
    status ai_prompt_status NOT NULL,
    error_message TEXT NULL,
    trace_id VARCHAR(100) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_prompt_logs_session
        FOREIGN KEY (session_id) REFERENCES ai_chat_sessions (session_id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_prompt_logs_message
        FOREIGN KEY (message_id) REFERENCES ai_chat_messages (message_id) ON DELETE SET NULL
);

COMMENT ON TABLE ai_prompt_logs IS 'Audits low-level model calls, payloads, token usage, and failures.';

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

CREATE TABLE IF NOT EXISTS ai_retrieval_logs (
    retrieval_id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NULL,
    message_id BIGINT NULL,
    user_id BIGINT NOT NULL,
    retrieval_mode VARCHAR(50) NULL,
    user_query TEXT NOT NULL,
    rewritten_query TEXT NULL,
    query_embedding_model VARCHAR(100) NULL,
    filters_json JSONB NULL,
    top_k INTEGER NOT NULL DEFAULT 5,
    results_json JSONB NOT NULL,
    latency_ms INTEGER NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_retrieval_logs_session
        FOREIGN KEY (session_id) REFERENCES ai_chat_sessions (session_id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_retrieval_logs_message
        FOREIGN KEY (message_id) REFERENCES ai_chat_messages (message_id) ON DELETE SET NULL
);

COMMENT ON TABLE ai_retrieval_logs IS 'Stores RAG retrieval traces for debugging and quality analysis.';

CREATE TABLE IF NOT EXISTS ai_feedback (
    feedback_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    feedback_type ai_feedback_type NOT NULL,
    comment_text TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_feedback_message
        FOREIGN KEY (message_id) REFERENCES ai_chat_messages (message_id) ON DELETE CASCADE,
    CONSTRAINT uq_ai_feedback_message_user_type UNIQUE (message_id, user_id, feedback_type)
);

COMMENT ON TABLE ai_feedback IS 'Stores user feedback about assistant responses.';

CREATE TABLE IF NOT EXISTS learner_global_profile_assets (
    profile_asset_id BIGSERIAL PRIMARY KEY,
    learner_id BIGINT NOT NULL,
    object_key VARCHAR(500) NOT NULL,
    version INTEGER NOT NULL,
    status ai_profile_asset_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_learner_global_profile_assets_learner_version UNIQUE (learner_id, version)
);

COMMENT ON TABLE learner_global_profile_assets IS 'Stores metadata mappings for learner global skills profile assets saved in object storage.';
COMMENT ON COLUMN learner_global_profile_assets.object_key IS 'Object storage key for the learner global skills profile asset.';

CREATE TABLE IF NOT EXISTS learner_module_profile_assets (
    profile_asset_id BIGSERIAL PRIMARY KEY,
    learner_id BIGINT NOT NULL,
    course_id BIGINT NOT NULL,
    module_id BIGINT NOT NULL,
    object_key VARCHAR(500) NOT NULL,
    version INTEGER NOT NULL,
    status ai_profile_asset_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_learner_module_profile_assets_scope_version UNIQUE (learner_id, course_id, module_id, version)
);

COMMENT ON TABLE learner_module_profile_assets IS 'Stores metadata mappings for learner module structured profile assets saved in object storage.';
COMMENT ON COLUMN learner_module_profile_assets.object_key IS 'Object storage key for the learner module structured profile asset.';

CREATE TABLE IF NOT EXISTS ai_knowledge_chunks (
    chunk_id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL,
    course_id BIGINT NULL,
    module_id BIGINT NULL,
    material_id BIGINT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INTEGER NULL,
    heading_path TEXT NULL,
    start_char INTEGER NULL,
    end_char INTEGER NULL,
    chunk_hash VARCHAR(128) NOT NULL,
    language_code VARCHAR(20) NULL,
    visibility_scope ai_visibility_scope NOT NULL DEFAULT 'course_only',
    publish_status ai_publish_status NOT NULL DEFAULT 'published',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    embedding_model VARCHAR(100) NOT NULL,
    embedding_version VARCHAR(50) NULL,
    embedding VECTOR(:AI_EMBEDDING_DIMENSION) NOT NULL,
    metadata_json JSONB NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_knowledge_chunks_source
        FOREIGN KEY (source_id) REFERENCES ai_knowledge_sources (source_id) ON DELETE CASCADE,
    CONSTRAINT uq_ai_knowledge_chunks_source_index UNIQUE (source_id, chunk_index)
);

COMMENT ON TABLE ai_knowledge_chunks IS 'Stores chunked knowledge text together with vector embeddings.';
COMMENT ON COLUMN ai_knowledge_chunks.embedding IS 'Vector embedding dimension is controlled by AI_EMBEDDING_DIMENSION.';

CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_user_id
    ON ai_chat_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_course_id
    ON ai_chat_sessions (course_id);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_module_id
    ON ai_chat_sessions (module_id);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_user_course
    ON ai_chat_sessions (user_id, course_id);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_last_message_at_desc
    ON ai_chat_sessions (last_message_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_session_created_at
    ON ai_chat_messages (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_parent_message_id
    ON ai_chat_messages (parent_message_id);
CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_role
    ON ai_chat_messages (role);
CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_created_at_desc
    ON ai_chat_messages (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_prompt_logs_session_id
    ON ai_prompt_logs (session_id);

CREATE INDEX IF NOT EXISTS idx_ai_embedding_logs_job_id
    ON ai_embedding_logs (job_id);

CREATE INDEX IF NOT EXISTS idx_ai_embedding_logs_material_id
    ON ai_embedding_logs (material_id);

CREATE INDEX IF NOT EXISTS idx_ai_embedding_logs_created_at
    ON ai_embedding_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_logs_message_id
    ON ai_prompt_logs (message_id);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_logs_user_id
    ON ai_prompt_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_logs_call_type
    ON ai_prompt_logs (call_type);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_logs_trace_id
    ON ai_prompt_logs (trace_id);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_logs_created_at_desc
    ON ai_prompt_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_retrieval_logs_session_id
    ON ai_retrieval_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_ai_retrieval_logs_message_id
    ON ai_retrieval_logs (message_id);
CREATE INDEX IF NOT EXISTS idx_ai_retrieval_logs_user_id
    ON ai_retrieval_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_ai_retrieval_logs_created_at_desc
    ON ai_retrieval_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_feedback_message_id
    ON ai_feedback (message_id);
CREATE INDEX IF NOT EXISTS idx_ai_feedback_user_id
    ON ai_feedback (user_id);
CREATE INDEX IF NOT EXISTS idx_ai_feedback_created_at_desc
    ON ai_feedback (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_learner_global_profile_assets_learner_status
    ON learner_global_profile_assets (learner_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_learner_module_profile_assets_scope_status
    ON learner_module_profile_assets (learner_id, course_id, module_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_index_jobs_status_priority_created_at
    ON ai_index_jobs (status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_index_jobs_status_next_retry_at
    ON ai_index_jobs (status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_ai_index_jobs_source_type_ref_id
    ON ai_index_jobs (source_type, source_ref_id);
CREATE INDEX IF NOT EXISTS idx_ai_index_jobs_course_id
    ON ai_index_jobs (course_id);
CREATE INDEX IF NOT EXISTS idx_ai_index_jobs_module_id
    ON ai_index_jobs (module_id);
CREATE INDEX IF NOT EXISTS idx_ai_index_jobs_material_id
    ON ai_index_jobs (material_id);
CREATE INDEX IF NOT EXISTS idx_ai_index_jobs_trigger_event_id
    ON ai_index_jobs (trigger_event_id);

CREATE INDEX IF NOT EXISTS idx_ai_consumed_events_status
    ON ai_consumed_events (status);
CREATE INDEX IF NOT EXISTS idx_ai_consumed_events_created_at_desc
    ON ai_consumed_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_knowledge_sources_course_id
    ON ai_knowledge_sources (course_id);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_sources_module_id
    ON ai_knowledge_sources (module_id);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_sources_material_id
    ON ai_knowledge_sources (material_id);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_sources_publish_status
    ON ai_knowledge_sources (publish_status);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_sources_visibility_scope
    ON ai_knowledge_sources (visibility_scope);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_sources_content_hash
    ON ai_knowledge_sources (content_hash);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_sources_origin_event_id
    ON ai_knowledge_sources (origin_event_id);

CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_source_id
    ON ai_knowledge_chunks (source_id);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_course_id
    ON ai_knowledge_chunks (course_id);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_module_id
    ON ai_knowledge_chunks (module_id);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_material_id
    ON ai_knowledge_chunks (material_id);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_is_active
    ON ai_knowledge_chunks (is_active);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_publish_status
    ON ai_knowledge_chunks (publish_status);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_visibility_scope
    ON ai_knowledge_chunks (visibility_scope);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_chunks_source_id_chunk_index
    ON ai_knowledge_chunks (source_id, chunk_index);
