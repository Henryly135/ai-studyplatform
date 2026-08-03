-- Gemini's July 2026 model lifecycle requires a new chat and embedding pair.
-- Gemini Embedding 2 uses a vector space that is incompatible with Embedding
-- 001, so deleting the retired catalog entry deliberately cascades its stored
-- vectors and source statuses. The normal reindex-all path repopulates the new
-- 1024-dimensional space after this migration.

INSERT INTO ai_model_catalog
    (
        model_id, provider_key, model_name, display_name, backend_supported,
        display_only, supports_chat, supports_json, supports_embedding,
        supports_rag_answer, supports_rag_indexing, embedding_dimension,
        paired_embedding_model_id, display_order, unavailable_reason
    )
VALUES
    (
        'gemini:gemini-embedding-2', 'gemini', 'gemini-embedding-2',
        'Gemini Embedding 2', TRUE, FALSE, FALSE, FALSE, TRUE, FALSE,
        TRUE, 1024, NULL, 19, NULL
    )
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

INSERT INTO ai_model_catalog
    (
        model_id, provider_key, model_name, display_name, backend_supported,
        display_only, supports_chat, supports_json, supports_embedding,
        supports_rag_answer, supports_rag_indexing, embedding_dimension,
        paired_embedding_model_id, display_order, unavailable_reason
    )
VALUES
    (
        'gemini:gemini-3.5-flash-lite', 'gemini',
        'gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite', TRUE, FALSE,
        TRUE, TRUE, FALSE, TRUE, FALSE, NULL,
        'gemini:gemini-embedding-2', 10, NULL
    ),
    (
        'gemini:gemini-3.6-flash', 'gemini',
        'gemini-3.6-flash', 'Gemini 3.6 Flash', TRUE, FALSE,
        TRUE, TRUE, FALSE, TRUE, FALSE, NULL,
        'gemini:gemini-embedding-2', 11, NULL
    )
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

UPDATE ai_user_model_preferences
SET chat_model_id = CASE
        WHEN chat_model_id IN (
            'gemini:gemini-2.5-flash-lite',
            'gemini:gemini-2.5-flash',
            'gemini:gemini-2.5-pro'
        ) THEN 'gemini:gemini-3.5-flash-lite'
        WHEN chat_model_id = 'openrouter:google/gemini-2.5-flash'
            THEN 'openrouter:openrouter/auto'
        ELSE chat_model_id
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE chat_model_id IN (
    'gemini:gemini-2.5-flash-lite',
    'gemini:gemini-2.5-flash',
    'gemini:gemini-2.5-pro',
    'openrouter:google/gemini-2.5-flash'
);

UPDATE ai_model_defaults
SET default_chat_model_id = CASE
        WHEN default_chat_model_id IN (
            'gemini:gemini-2.5-flash-lite',
            'gemini:gemini-2.5-flash',
            'gemini:gemini-2.5-pro'
        ) THEN 'gemini:gemini-3.5-flash-lite'
        WHEN default_chat_model_id = 'openrouter:google/gemini-2.5-flash'
            THEN 'openrouter:openrouter/auto'
        ELSE default_chat_model_id
    END,
    default_embedding_model_id = CASE
        WHEN default_embedding_model_id = 'gemini:gemini-embedding-001'
            THEN 'gemini:gemini-embedding-2'
        ELSE default_embedding_model_id
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE default_chat_model_id IN (
        'gemini:gemini-2.5-flash-lite',
        'gemini:gemini-2.5-flash',
        'gemini:gemini-2.5-pro',
        'openrouter:google/gemini-2.5-flash'
    )
   OR default_embedding_model_id = 'gemini:gemini-embedding-001';

UPDATE ai_model_defaults AS defaults
SET default_embedding_model_id = catalog.paired_embedding_model_id,
    updated_at = CURRENT_TIMESTAMP
FROM ai_model_catalog AS catalog
WHERE catalog.model_id = defaults.default_chat_model_id
  AND catalog.paired_embedding_model_id IS NOT NULL
  AND defaults.default_embedding_model_id IS DISTINCT FROM
      catalog.paired_embedding_model_id;

WITH retired_models AS (
    DELETE FROM ai_model_catalog
    WHERE model_id IN (
        'gemini:gemini-2.5-flash-lite',
        'gemini:gemini-2.5-flash',
        'gemini:gemini-2.5-pro',
        'gemini:gemini-embedding-001',
        'openrouter:google/gemini-2.5-flash'
    )
    RETURNING provider_key
)
UPDATE ai_provider_credentials
SET health_status = 'unknown',
    last_checked_at = NULL,
    last_error = NULL,
    updated_at = CURRENT_TIMESTAMP
WHERE provider_key = 'gemini'
  AND EXISTS (
      SELECT 1
      FROM retired_models
      WHERE provider_key = 'gemini'
  );
