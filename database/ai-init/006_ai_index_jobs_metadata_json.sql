ALTER TABLE ai_index_jobs
    ADD COLUMN IF NOT EXISTS metadata_json JSONB NULL;
