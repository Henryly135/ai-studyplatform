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
