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

CREATE INDEX IF NOT EXISTS idx_learner_module_profile_assets_scope_status
    ON learner_module_profile_assets (learner_id, course_id, module_id, status, updated_at DESC);
