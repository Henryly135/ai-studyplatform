SET @ddl = IF(
    (
        SELECT COUNT(1)
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'course_forum_posts'
          AND column_name = 'is_pinned'
    ) = 0,
    'ALTER TABLE course_forum_posts ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT FALSE AFTER metadata_json',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = IF(
    (
        SELECT COUNT(1)
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'course_forum_posts'
          AND column_name = 'pinned_at'
    ) = 0,
    'ALTER TABLE course_forum_posts ADD COLUMN pinned_at DATETIME NULL AFTER is_pinned',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = IF(
    (
        SELECT COUNT(1)
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'course_forum_posts'
          AND column_name = 'pinned_by_user_id'
    ) = 0,
    'ALTER TABLE course_forum_posts ADD COLUMN pinned_by_user_id BIGINT NULL AFTER pinned_at',
    'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
