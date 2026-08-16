DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_message_generation_status') THEN
        CREATE TYPE ai_message_generation_status AS ENUM ('pending', 'completed', 'failed');
    END IF;
END
$$;

ALTER TABLE ai_chat_messages
    ADD COLUMN IF NOT EXISTS client_request_id VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS requested_model_id VARCHAR(160) NULL,
    ADD COLUMN IF NOT EXISTS generation_status ai_message_generation_status NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS failure_code VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS failure_message TEXT NULL,
    ADD COLUMN IF NOT EXISTS generation_attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS generation_started_at TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS generation_completed_at TIMESTAMP NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_chat_messages_client_request_id
    ON ai_chat_messages (client_request_id)
    WHERE client_request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_generation_status
    ON ai_chat_messages (generation_status, created_at DESC);

COMMENT ON COLUMN ai_chat_messages.client_request_id IS 'Client-generated idempotency key for a user chat request.';
COMMENT ON COLUMN ai_chat_messages.generation_status IS 'Pending, completed, or failed state of assistant generation for a user message.';
