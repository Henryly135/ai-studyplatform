ALTER TABLE modules
    ADD COLUMN content TEXT NULL AFTER description,
    ADD COLUMN status ENUM('draft', 'published', 'archived') NOT NULL DEFAULT 'draft' AFTER estimated_minutes,
    ADD COLUMN visible_to_class_id VARCHAR(100) NULL AFTER status,
    DROP COLUMN is_published;
