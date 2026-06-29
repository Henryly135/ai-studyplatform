ALTER TABLE ai_index_jobs
    ALTER COLUMN source_version TYPE VARCHAR(500);

ALTER TABLE ai_knowledge_sources
    ALTER COLUMN source_version TYPE VARCHAR(500);
