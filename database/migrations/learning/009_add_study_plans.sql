CREATE TABLE IF NOT EXISTS study_plans (
    plan_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    plan_uuid VARCHAR(36) NOT NULL,
    learner_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    status ENUM('active', 'archived') NOT NULL DEFAULT 'active',
    input_json JSON NOT NULL,
    plan_json JSON NOT NULL,
    provider_name VARCHAR(100) NULL,
    provider_model VARCHAR(160) NULL,
    used_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    fallback_reason VARCHAR(200) NULL,
    adjustment_notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_study_plans_uuid UNIQUE (plan_uuid)
) COMMENT='Learner-visible generated study planner records and adjustable plan content.';
