CREATE TABLE IF NOT EXISTS ai_model_providers (
    provider_key VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    adapter_type VARCHAR(50) NOT NULL,
    default_base_url VARCHAR(500) NULL,
    backend_supported BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_model_catalog (
    model_id VARCHAR(120) PRIMARY KEY,
    provider_key VARCHAR(50) NOT NULL REFERENCES ai_model_providers(provider_key) ON DELETE CASCADE,
    model_name VARCHAR(160) NOT NULL,
    display_name VARCHAR(160) NOT NULL,
    backend_supported BOOLEAN NOT NULL DEFAULT FALSE,
    display_only BOOLEAN NOT NULL DEFAULT FALSE,
    supports_chat BOOLEAN NOT NULL DEFAULT FALSE,
    supports_json BOOLEAN NOT NULL DEFAULT FALSE,
    supports_embedding BOOLEAN NOT NULL DEFAULT FALSE,
    supports_rag_answer BOOLEAN NOT NULL DEFAULT FALSE,
    supports_rag_indexing BOOLEAN NOT NULL DEFAULT FALSE,
    embedding_dimension INTEGER NULL,
    paired_embedding_model_id VARCHAR(120) NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER NOT NULL DEFAULT 100,
    unavailable_reason TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ai_model_catalog_provider_model UNIQUE (provider_key, model_name)
);

ALTER TABLE ai_model_catalog
    ADD COLUMN IF NOT EXISTS paired_embedding_model_id VARCHAR(120) NULL;

CREATE TABLE IF NOT EXISTS ai_provider_credentials (
    provider_key VARCHAR(50) PRIMARY KEY REFERENCES ai_model_providers(provider_key) ON DELETE CASCADE,
    encrypted_api_key TEXT NULL,
    api_key_hint VARCHAR(16) NULL,
    base_url_override VARCHAR(500) NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    health_status VARCHAR(30) NOT NULL DEFAULT 'unknown',
    last_checked_at TIMESTAMP NULL,
    last_error TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_user_model_preferences (
    user_id BIGINT PRIMARY KEY,
    chat_model_id VARCHAR(120) NOT NULL REFERENCES ai_model_catalog(model_id) ON DELETE RESTRICT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_model_defaults (
    scope_key VARCHAR(50) PRIMARY KEY,
    default_chat_model_id VARCHAR(120) NULL REFERENCES ai_model_catalog(model_id) ON DELETE SET NULL,
    default_embedding_model_id VARCHAR(120) NULL REFERENCES ai_model_catalog(model_id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO ai_model_providers
    (provider_key, display_name, adapter_type, default_base_url, backend_supported, display_order)
VALUES
    ('gemini', 'Gemini', 'gemini', NULL, TRUE, 10),
    ('glm', 'GLM', 'openai_compatible', 'https://open.bigmodel.cn/api/paas/v4', TRUE, 20),
    ('openrouter', 'OpenRouter', 'openai_compatible', 'https://openrouter.ai/api/v1', TRUE, 30)
ON CONFLICT (provider_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    adapter_type = EXCLUDED.adapter_type,
    default_base_url = EXCLUDED.default_base_url,
    backend_supported = EXCLUDED.backend_supported,
    display_order = EXCLUDED.display_order,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO ai_model_catalog
    (
        model_id, provider_key, model_name, display_name, backend_supported, display_only,
        supports_chat, supports_json, supports_embedding, supports_rag_answer, supports_rag_indexing,
        embedding_dimension, paired_embedding_model_id, display_order, unavailable_reason
    )
VALUES
    ('gemini:gemini-3.5-flash-lite', 'gemini', 'gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite', TRUE, FALSE, TRUE, TRUE, FALSE, TRUE, FALSE, NULL, 'gemini:gemini-embedding-2', 10, NULL),
    ('gemini:gemini-3.6-flash', 'gemini', 'gemini-3.6-flash', 'Gemini 3.6 Flash', TRUE, FALSE, TRUE, TRUE, FALSE, TRUE, FALSE, NULL, 'gemini:gemini-embedding-2', 11, NULL),
    ('gemini:gemini-embedding-2', 'gemini', 'gemini-embedding-2', 'Gemini Embedding 2', TRUE, FALSE, FALSE, FALSE, TRUE, FALSE, TRUE, 1024, NULL, 19, NULL),
    ('glm:glm-4.7', 'glm', 'glm-4.7', 'GLM 4.7', TRUE, FALSE, TRUE, TRUE, FALSE, TRUE, FALSE, NULL, 'glm:embedding-3', 21, NULL),
    ('glm:embedding-3', 'glm', 'embedding-3', 'GLM Embedding-3', TRUE, FALSE, FALSE, FALSE, TRUE, FALSE, TRUE, 1024, NULL, 29, NULL),
    ('openrouter:openrouter/auto', 'openrouter', 'openrouter/auto', 'OpenRouter Auto', TRUE, FALSE, TRUE, TRUE, FALSE, TRUE, FALSE, NULL, 'openrouter:openai/text-embedding-3-small', 30, NULL),
    ('openrouter:openai/text-embedding-3-small', 'openrouter', 'openai/text-embedding-3-small', 'OpenAI Text Embedding 3 Small via OpenRouter', TRUE, FALSE, FALSE, FALSE, TRUE, FALSE, TRUE, 1024, NULL, 39, NULL)
ON CONFLICT (model_id) DO UPDATE SET
    provider_key = EXCLUDED.provider_key,
    model_name = EXCLUDED.model_name,
    display_name = EXCLUDED.display_name,
    backend_supported = EXCLUDED.backend_supported,
    display_only = EXCLUDED.display_only,
    supports_chat = EXCLUDED.supports_chat,
    supports_json = EXCLUDED.supports_json,
    supports_embedding = EXCLUDED.supports_embedding,
    supports_rag_answer = EXCLUDED.supports_rag_answer,
    supports_rag_indexing = EXCLUDED.supports_rag_indexing,
    embedding_dimension = EXCLUDED.embedding_dimension,
    paired_embedding_model_id = EXCLUDED.paired_embedding_model_id,
    display_order = EXCLUDED.display_order,
    unavailable_reason = EXCLUDED.unavailable_reason,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO ai_model_defaults (scope_key, default_chat_model_id, default_embedding_model_id)
VALUES ('global', 'gemini:gemini-3.5-flash-lite', 'gemini:gemini-embedding-2')
ON CONFLICT (scope_key) DO NOTHING;

UPDATE ai_model_defaults AS defaults
SET default_chat_model_id = 'gemini:gemini-3.5-flash-lite',
    default_embedding_model_id = 'gemini:gemini-embedding-2',
    updated_at = CURRENT_TIMESTAMP
WHERE defaults.default_chat_model_id LIKE 'deepseek:%';

DELETE FROM ai_user_model_preferences
WHERE chat_model_id LIKE 'deepseek:%';

DELETE FROM ai_model_providers
WHERE provider_key = 'deepseek';

UPDATE ai_model_defaults AS defaults
SET default_embedding_model_id = catalog.paired_embedding_model_id,
    updated_at = CURRENT_TIMESTAMP
FROM ai_model_catalog AS catalog
WHERE catalog.model_id = defaults.default_chat_model_id
  AND catalog.paired_embedding_model_id IS NOT NULL
  AND defaults.default_embedding_model_id IS DISTINCT FROM catalog.paired_embedding_model_id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_ai_model_catalog_paired_embedding_model'
          AND conrelid = 'ai_model_catalog'::regclass
    ) THEN
        ALTER TABLE ai_model_catalog
            ADD CONSTRAINT fk_ai_model_catalog_paired_embedding_model
            FOREIGN KEY (paired_embedding_model_id)
            REFERENCES ai_model_catalog(model_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_ai_model_catalog_provider_key ON ai_model_catalog (provider_key);
CREATE INDEX IF NOT EXISTS idx_ai_model_catalog_display_order ON ai_model_catalog (display_order);
CREATE INDEX IF NOT EXISTS idx_ai_model_catalog_paired_embedding_model_id
    ON ai_model_catalog (paired_embedding_model_id);
