-- GLM 4.5 is retired from the controlled catalog in favor of GLM 4.7.
-- The paired embedding model is unchanged, so existing GLM Embedding-3
-- vectors remain valid and do not require a vector-space migration.

UPDATE ai_user_model_preferences
SET chat_model_id = 'glm:glm-4.7',
    updated_at = CURRENT_TIMESTAMP
WHERE chat_model_id = 'glm:glm-4.5-air';

UPDATE ai_model_defaults
SET default_chat_model_id = 'glm:glm-4.7',
    default_embedding_model_id = 'glm:embedding-3',
    updated_at = CURRENT_TIMESTAMP
WHERE default_chat_model_id = 'glm:glm-4.5-air';

WITH retired_models AS (
    DELETE FROM ai_model_catalog
    WHERE model_id = 'glm:glm-4.5-air'
    RETURNING model_id
)
UPDATE ai_provider_credentials
SET health_status = 'unknown',
    last_checked_at = NULL,
    last_error = NULL,
    updated_at = CURRENT_TIMESTAMP
WHERE provider_key = 'glm'
  AND EXISTS (SELECT 1 FROM retired_models);
