CREATE TABLE IF NOT EXISTS courses (
    course_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    educator_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(255) NULL,
    description TEXT NULL,
    cover_image_url VARCHAR(500) NULL,
    status ENUM('draft', 'published', 'archived') NOT NULL DEFAULT 'draft',
    difficulty_level ENUM('beginner', 'intermediate', 'advanced') NULL,
    estimated_minutes INT NULL,
    category VARCHAR(100) NULL,
    language_code VARCHAR(20) NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    published_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='Stores course business entities, educator ownership, and publishing metadata.';

CREATE TABLE IF NOT EXISTS learning_paths (
    learning_path_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    course_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_learning_paths_course_id UNIQUE (course_id),
    CONSTRAINT fk_learning_paths_course FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
) COMMENT='Stores the single ordered learning path attached to each course.';

CREATE TABLE IF NOT EXISTS modules (
    module_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    learning_path_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NULL,
    content TEXT NULL,
    sort_order INT NOT NULL,
    estimated_minutes INT NULL,
    status ENUM('draft', 'published', 'archived') NOT NULL DEFAULT 'draft',
    visible_to_class_id VARCHAR(100) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_modules_path_sort_order UNIQUE (learning_path_id, sort_order),
    CONSTRAINT fk_modules_learning_path FOREIGN KEY (learning_path_id) REFERENCES learning_paths (learning_path_id) ON DELETE CASCADE
) COMMENT='Stores modules within a learning path; order controls educator drag-and-drop sequencing and learner unlock flow.';

CREATE TABLE IF NOT EXISTS module_materials (
    material_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    module_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    material_type ENUM('pdf', 'video', 'file', 'link', 'text') NOT NULL,
    resource_url VARCHAR(1000) NOT NULL,
    sort_order INT NOT NULL,
    metadata_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_materials_module_sort_order UNIQUE (module_id, sort_order),
    CONSTRAINT fk_module_materials_module FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE
) COMMENT='Stores ordered learning materials belonging to a module.';

CREATE TABLE IF NOT EXISTS module_material_upload_sessions (
    upload_session_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_uuid VARCHAR(64) NOT NULL,
    module_id BIGINT NOT NULL,
    created_by_user_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    material_type ENUM('pdf', 'video', 'file', 'link', 'text') NOT NULL,
    sort_order INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(255) NULL,
    size_bytes BIGINT NULL,
    storage_provider VARCHAR(20) NOT NULL,
    bucket VARCHAR(100) NULL,
    object_key VARCHAR(500) NOT NULL,
    multipart_upload_id VARCHAR(255) NOT NULL,
    status ENUM('initiated', 'uploading', 'completed', 'aborted', 'failed') NOT NULL DEFAULT 'initiated',
    material_id BIGINT NULL,
    metadata_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_material_upload_sessions_uuid UNIQUE (session_uuid),
    CONSTRAINT fk_module_material_upload_sessions_module FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE,
    CONSTRAINT fk_module_material_upload_sessions_material FOREIGN KEY (material_id) REFERENCES module_materials (material_id) ON DELETE SET NULL
) COMMENT='Stores multipart upload sessions for large module materials before the final material record is created.';

CREATE TABLE IF NOT EXISTS module_prerequisites (
    module_prerequisite_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    module_id BIGINT NOT NULL,
    prerequisite_module_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_prerequisites_module_id UNIQUE (module_id),
    CONSTRAINT uq_module_prerequisites_pair UNIQUE (prerequisite_module_id, module_id),
    CONSTRAINT fk_module_prerequisites_module FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE,
    CONSTRAINT fk_module_prerequisites_prerequisite FOREIGN KEY (prerequisite_module_id) REFERENCES modules (module_id) ON DELETE CASCADE
) COMMENT='Stores prerequisite progression rules such as Module A must be completed before Module B.';

CREATE TABLE IF NOT EXISTS course_enrollments (
    enrollment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    course_id BIGINT NOT NULL,
    learner_id BIGINT NOT NULL,
    enrollment_status ENUM('active', 'completed', 'dropped') NOT NULL DEFAULT 'active',
    progress_percent DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    completed_module_count INT NOT NULL DEFAULT 0,
    total_module_count INT NOT NULL DEFAULT 0,
    last_accessed_at DATETIME NULL,
    enrolled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_course_enrollments_course_learner UNIQUE (course_id, learner_id),
    CONSTRAINT fk_course_enrollments_course FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
) COMMENT='Stores learner enrollment in a course together with course-level progress summary fields.';

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

CREATE TABLE IF NOT EXISTS module_progress (
    module_progress_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    module_id BIGINT NOT NULL,
    learner_id BIGINT NOT NULL,
    progress_status ENUM('not_started', 'in_progress', 'completed') NOT NULL DEFAULT 'not_started',
    progress_percent DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    time_spent_seconds INT NOT NULL DEFAULT 0,
    started_at DATETIME NULL,
    last_accessed_at DATETIME NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_progress_module_learner UNIQUE (module_id, learner_id),
    CONSTRAINT fk_module_progress_module FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE
) COMMENT='Stores learner progress for each module and serves as the basis for sequential unlock behavior.';

CREATE TABLE IF NOT EXISTS quizzes (
    quiz_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    module_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NULL,
    status ENUM('draft', 'published', 'archived') NOT NULL DEFAULT 'draft',
    time_limit_seconds INT NULL,
    question_count_per_attempt INT NOT NULL,
    shuffle_questions BOOLEAN NOT NULL DEFAULT TRUE,
    shuffle_options BOOLEAN NOT NULL DEFAULT FALSE,
    passing_rule ENUM('all_correct') NOT NULL DEFAULT 'all_correct',
    published_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_quizzes_module_id UNIQUE (module_id),
    CONSTRAINT fk_quizzes_module FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE
) COMMENT='Stores the single quiz configuration attached to each module.';

CREATE TABLE IF NOT EXISTS quiz_questions (
    quiz_question_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    quiz_id BIGINT NOT NULL,
    question_text TEXT NOT NULL,
    explanation_text TEXT NULL,
    source_grounding TEXT NULL,
    sort_order INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_quiz_questions_quiz_sort_order UNIQUE (quiz_id, sort_order),
    CONSTRAINT fk_quiz_questions_quiz FOREIGN KEY (quiz_id) REFERENCES quizzes (quiz_id) ON DELETE CASCADE
) COMMENT='Stores the question bank for a quiz; attempts randomly draw from active questions.';

CREATE TABLE IF NOT EXISTS quiz_question_options (
    quiz_question_option_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    quiz_question_id BIGINT NOT NULL,
    option_label VARCHAR(10) NULL,
    option_text TEXT NOT NULL,
    sort_order INT NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_quiz_question_options_question_sort_order UNIQUE (quiz_question_id, sort_order),
    CONSTRAINT fk_quiz_question_options_question FOREIGN KEY (quiz_question_id) REFERENCES quiz_questions (quiz_question_id) ON DELETE CASCADE
) COMMENT='Stores selectable options for a single-choice quiz question.';

CREATE TABLE IF NOT EXISTS quiz_attempts (
    quiz_attempt_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    quiz_id BIGINT NOT NULL,
    module_id BIGINT NOT NULL,
    learner_id BIGINT NOT NULL,
    attempt_number INT NOT NULL,
    question_count INT NOT NULL,
    correct_count INT NOT NULL DEFAULT 0,
    score_percent DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    is_passed BOOLEAN NOT NULL DEFAULT FALSE,
    is_timed_out BOOLEAN NOT NULL DEFAULT FALSE,
    time_limit_seconds_snapshot INT NULL,
    started_at DATETIME NOT NULL,
    submitted_at DATETIME NOT NULL,
    duration_seconds INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_quiz_attempts_quiz_learner_attempt_number UNIQUE (quiz_id, learner_id, attempt_number),
    CONSTRAINT fk_quiz_attempts_quiz FOREIGN KEY (quiz_id) REFERENCES quizzes (quiz_id) ON DELETE CASCADE,
    CONSTRAINT fk_quiz_attempts_module FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE
) COMMENT='Stores every learner submission attempt for a quiz, including scoring, timing, and pass outcome.';

CREATE TABLE IF NOT EXISTS quiz_attempt_answers (
    quiz_attempt_answer_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    quiz_attempt_id BIGINT NOT NULL,
    quiz_question_id BIGINT NOT NULL,
    selected_option_id BIGINT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT FALSE,
    question_order INT NOT NULL,
    question_text_snapshot TEXT NOT NULL,
    explanation_text_snapshot TEXT NULL,
    selected_option_text_snapshot TEXT NULL,
    correct_option_id_snapshot BIGINT NOT NULL,
    correct_option_text_snapshot TEXT NOT NULL,
    option_order_snapshot_json JSON NOT NULL,
    option_texts_snapshot_json JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_quiz_attempt_answers_attempt_question UNIQUE (quiz_attempt_id, quiz_question_id),
    CONSTRAINT uq_quiz_attempt_answers_attempt_order UNIQUE (quiz_attempt_id, question_order),
    CONSTRAINT fk_quiz_attempt_answers_attempt FOREIGN KEY (quiz_attempt_id) REFERENCES quiz_attempts (quiz_attempt_id) ON DELETE CASCADE,
    CONSTRAINT fk_quiz_attempt_answers_question FOREIGN KEY (quiz_question_id) REFERENCES quiz_questions (quiz_question_id) ON DELETE RESTRICT,
    CONSTRAINT fk_quiz_attempt_answers_selected_option FOREIGN KEY (selected_option_id) REFERENCES quiz_question_options (quiz_question_option_id) ON DELETE RESTRICT
) COMMENT='Stores per-question answer results for a quiz attempt together with immutable question and option snapshots.';

CREATE TABLE IF NOT EXISTS course_invite_tokens (
    invite_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    invite_uuid VARCHAR(36) NOT NULL,
    token_hash VARCHAR(255) NULL,
    course_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_course_invite_tokens_uuid UNIQUE (invite_uuid),
    CONSTRAINT fk_course_invite_tokens_course FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
) COMMENT='Reusable invite links for learners to self-enrol into courses, generated by educators.';

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
