ALTER TABLE learner_global_profile_assets
    ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN learner_global_profile_assets.preferences IS
    'Structured learner preferences used to render and regenerate the global profile';
