CREATE TABLE IF NOT EXISTS course_forum_posts (
    post_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    course_id BIGINT NOT NULL,
    author_user_id BIGINT NOT NULL,
    author_email VARCHAR(255) NOT NULL,
    author_name VARCHAR(255) NOT NULL,
    post_kind ENUM('user', 'system') NOT NULL DEFAULT 'user',
    title VARCHAR(200) NULL,
    content TEXT NOT NULL,
    metadata_json JSON NULL,
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
    pinned_at DATETIME NULL,
    pinned_by_user_id BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='Stores forum posts scoped to a course, including both user-authored and system-authored posts.';

CREATE TABLE IF NOT EXISTS course_forum_comments (
    comment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    post_id BIGINT NOT NULL,
    course_id BIGINT NOT NULL,
    author_user_id BIGINT NOT NULL,
    author_email VARCHAR(255) NOT NULL,
    author_name VARCHAR(255) NOT NULL,
    root_comment_id BIGINT NULL,
    reply_to_comment_id BIGINT NULL,
    comment_kind ENUM('user', 'system') NOT NULL DEFAULT 'user',
    content TEXT NOT NULL,
    metadata_json JSON NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_course_forum_comments_post
        FOREIGN KEY (post_id) REFERENCES course_forum_posts (post_id) ON DELETE CASCADE,
    CONSTRAINT fk_course_forum_comments_root_comment
        FOREIGN KEY (root_comment_id) REFERENCES course_forum_comments (comment_id) ON DELETE CASCADE,
    CONSTRAINT fk_course_forum_comments_reply_to_comment
        FOREIGN KEY (reply_to_comment_id) REFERENCES course_forum_comments (comment_id) ON DELETE SET NULL
) COMMENT='Stores top-level comments and flattened reply threads for forum posts; replies stay attached to the root comment while preserving the direct reply target.';

CREATE TABLE IF NOT EXISTS notifications (
    notification_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    notification_type VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    actor_user_id BIGINT NULL,
    actor_email VARCHAR(255) NULL,
    actor_name VARCHAR(255) NULL,
    target_type VARCHAR(100) NULL,
    target_id VARCHAR(191) NULL,
    metadata_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='Stores notification content and target metadata before it is fanned out to individual recipients.';

CREATE TABLE IF NOT EXISTS notification_recipients (
    notification_recipient_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    notification_id BIGINT NOT NULL,
    recipient_user_id BIGINT NOT NULL,
    recipient_email VARCHAR(255) NOT NULL,
    recipient_name VARCHAR(255) NOT NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    read_at DATETIME NULL,
    is_hidden TINYINT(1) NOT NULL DEFAULT 0,
    hidden_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_notification_recipients_notification
        FOREIGN KEY (notification_id) REFERENCES notifications (notification_id)
        ON DELETE CASCADE,
    CONSTRAINT uq_notification_recipients_notification_user
        UNIQUE (notification_id, recipient_user_id)
) COMMENT='Stores per-recipient read and visibility state for each notification.';
