CREATE TABLE IF NOT EXISTS course_enrollment_audit_logs (
    audit_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    enrollment_id BIGINT NOT NULL,
    course_id BIGINT NOT NULL,
    learner_id BIGINT NOT NULL,
    action_type ENUM('enrolled', 'dropped', 're_enrolled', 'completed', 'status_changed') NOT NULL,
    changed_by_user_id BIGINT NULL,
    changed_by_role ENUM('learner', 'educator', 'admin', 'system') NOT NULL,
    old_status VARCHAR(20) NULL,
    new_status VARCHAR(20) NOT NULL,
    reason TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_course_enrollment_audit_logs_enrollment FOREIGN KEY (enrollment_id) REFERENCES course_enrollments (enrollment_id) ON DELETE CASCADE,
    CONSTRAINT fk_course_enrollment_audit_logs_course FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
) COMMENT='Records every enrollment status transition together with actor, reason, and timing for auditability.';

CREATE INDEX idx_course_enrollment_audit_logs_enrollment_id
    ON course_enrollment_audit_logs (enrollment_id);

CREATE INDEX idx_course_enrollment_audit_logs_course_id
    ON course_enrollment_audit_logs (course_id);

CREATE INDEX idx_course_enrollment_audit_logs_learner_id
    ON course_enrollment_audit_logs (learner_id);

CREATE INDEX idx_course_enrollment_audit_logs_created_at
    ON course_enrollment_audit_logs (created_at);
