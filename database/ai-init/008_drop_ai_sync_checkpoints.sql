DROP TABLE IF EXISTS ai_sync_checkpoints;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_sync_type') THEN
        DROP TYPE ai_sync_type;
    END IF;
END
$$;
