DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_profile_asset_status') THEN
        CREATE TYPE ai_profile_asset_status AS ENUM ('active', 'archived');
    END IF;
END
$$;

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

CREATE INDEX IF NOT EXISTS idx_learner_global_profile_assets_learner_status
    ON learner_global_profile_assets (learner_id, status, updated_at DESC);
