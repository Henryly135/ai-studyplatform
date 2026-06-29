SET @ddl = IF(
    (
        SELECT COUNT(1)
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'quiz_questions'
          AND column_name = 'source_grounding'
    ) = 0,
    'ALTER TABLE quiz_questions ADD COLUMN source_grounding TEXT NULL AFTER explanation_text',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
