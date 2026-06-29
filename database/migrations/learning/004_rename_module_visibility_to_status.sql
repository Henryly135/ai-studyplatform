ALTER TABLE modules
    CHANGE COLUMN visibility status ENUM('draft', 'published', 'archived') NOT NULL DEFAULT 'draft';
