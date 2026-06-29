DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_job_status')
        AND NOT EXISTS (
            SELECT 1
            FROM pg_enum
            WHERE enumtypid = 'ai_job_status'::regtype
              AND enumlabel = 'blocked'
        ) THEN
        ALTER TYPE ai_job_status ADD VALUE 'blocked' BEFORE 'queued';
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_ai_index_jobs_status_next_retry_at
    ON ai_index_jobs (status, next_retry_at);
