CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    account_status ENUM('active', 'pending', 'rejected', 'deactivated') NOT NULL DEFAULT 'pending',
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at DATETIME NULL,
    CONSTRAINT uq_users_email UNIQUE (email)
) COMMENT='Stores user account credentials, profile basics, and account status.';

CREATE TABLE IF NOT EXISTS roles (
    role_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    role_code VARCHAR(50) NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    description VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_roles_role_code UNIQUE (role_code),
    CONSTRAINT uq_roles_role_name UNIQUE (role_name)
) COMMENT='Defines system roles used by the RBAC permission model.';

CREATE TABLE IF NOT EXISTS permissions (
    permission_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    permission_code VARCHAR(100) NOT NULL,
    permission_name VARCHAR(100) NOT NULL,
    description VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_permissions_permission_code UNIQUE (permission_code),
    CONSTRAINT uq_permissions_permission_name UNIQUE (permission_name)
) COMMENT='Defines individual permission codes that can be granted to roles.';

CREATE TABLE IF NOT EXISTS user_roles (
    user_role_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_roles_user_role UNIQUE (user_id, role_id),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE CASCADE
) COMMENT='Maps users to one or more assigned roles.';

CREATE TABLE IF NOT EXISTS role_permissions (
    role_permission_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    role_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_role_permissions_role_permission UNIQUE (role_id, permission_id),
    CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES permissions (permission_id) ON DELETE CASCADE
) COMMENT='Maps roles to the permissions they are allowed to perform.';

CREATE TABLE IF NOT EXISTS educator_approval_requests (
    request_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    supporting_info TEXT NULL,
    supporting_file_url VARCHAR(500) NULL,
    request_status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME NULL,
    reviewed_by BIGINT NULL,
    review_comment TEXT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_educator_approval_requests_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_educator_approval_requests_reviewer FOREIGN KEY (reviewed_by) REFERENCES users (user_id) ON DELETE SET NULL
) COMMENT='Tracks educator registration approval requests and review outcomes.';

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    token_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_email_verification_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_email_verification_tokens_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) COMMENT='Stores hashed email verification tokens for account activation.';

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_password_reset_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_password_reset_tokens_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) COMMENT='Stores hashed password reset tokens for secure password recovery.';

CREATE TABLE IF NOT EXISTS user_role_audit_logs (
    audit_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    target_user_id BIGINT NOT NULL,
    changed_by BIGINT NULL,
    change_type ENUM('role_change', 'status_change', 'approval_result') NOT NULL,
    old_role_id BIGINT NULL,
    new_role_id BIGINT NULL,
    old_status ENUM('active', 'pending', 'rejected', 'deactivated') NULL,
    new_status ENUM('active', 'pending', 'rejected', 'deactivated') NULL,
    change_reason TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_role_audit_logs_target_user FOREIGN KEY (target_user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_role_audit_logs_changed_by FOREIGN KEY (changed_by) REFERENCES users (user_id) ON DELETE SET NULL,
    CONSTRAINT fk_user_role_audit_logs_old_role FOREIGN KEY (old_role_id) REFERENCES roles (role_id) ON DELETE SET NULL,
    CONSTRAINT fk_user_role_audit_logs_new_role FOREIGN KEY (new_role_id) REFERENCES roles (role_id) ON DELETE SET NULL
) COMMENT='Records role and account status changes for auditing and traceability.';

CREATE TABLE IF NOT EXISTS login_audit_logs (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NULL,
    email_attempted VARCHAR(255) NOT NULL,
    login_result ENUM('success', 'failed') NOT NULL,
    failure_reason VARCHAR(255) NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_login_audit_logs_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL
) COMMENT='Records login attempts, outcomes, and request metadata for security analysis.';

INSERT INTO roles (role_code, role_name, description)
VALUES
    ('learner', 'Learner', 'Default learner role'),
    ('educator', 'Educator', 'Educator role for approved teaching accounts'),
    ('admin', 'Admin', 'Administrative role')
ON DUPLICATE KEY UPDATE
    role_name = VALUES(role_name),
    description = VALUES(description);

INSERT INTO permissions (permission_code, permission_name, description)
VALUES
    ('user.read', 'Read user', 'View user details'),
    ('user.update', 'Update user', 'Update user details'),
    ('user.activate', 'Activate user', 'Activate user account'),
    ('user.deactivate', 'Deactivate user', 'Deactivate user account'),
    ('educator_approval.read', 'Read educator approvals', 'View educator approval requests'),
    ('educator_approval.review', 'Review educator approvals', 'Approve or reject educator requests'),
    ('role.assign', 'Assign role', 'Assign roles to users'),
    ('course.create', 'Create course', 'Create course records'),
    ('course.update', 'Update course', 'Update course records'),
    ('course.publish', 'Publish course', 'Publish course records'),
    ('course.enrol', 'Enrol course', 'Enrol in courses as a learner'),
    ('course_enrollment.manage', 'Manage course enrollment', 'Manage learner enrollment status for courses'),
    ('resource.upload', 'Upload resources', 'Upload learning resources'),
    ('resource.manage', 'Manage resources', 'Manage uploaded learning resources'),
    ('learning_path.create', 'Create learning path', 'Create learning paths'),
    ('learning_path.update', 'Update learning path', 'Update learning paths'),
    ('learning_path.delete', 'Delete learning path', 'Delete learning paths'),
    ('learning_path.manage', 'Manage learning path', 'Manage learning paths end-to-end'),
    ('module.create', 'Create module', 'Create course modules'),
    ('module.update', 'Update module', 'Update course modules'),
    ('module.delete', 'Delete module', 'Delete course modules'),
    ('module.publish', 'Publish module', 'Publish or change module visibility'),
    ('forum.read', 'Read forum', 'View course forum posts and comments'),
    ('forum.write', 'Write forum', 'Create and manage own course forum posts and comments'),
    ('forum.pin', 'Pin forum posts', 'Pin and unpin forum posts for courses you moderate'),
    ('notification.read', 'Read notifications', 'View and manage personal notifications'),
    ('notification.manage', 'Manage notifications', 'Create, update and delete system notifications'),
    ('ai.chat.use', 'Use AI chat', 'Use AI chat features'),
    ('learner_profile.manage', 'Manage learner profile', 'Create and view learner global profile settings'),
    ('quiz.attempt', 'Attempt quiz', 'Start and submit learner quiz attempts'),
    ('ai.governance.manage', 'Manage AI governance', 'Retry AI indexing jobs and perform AI governance recovery actions'),
    ('audit_log.read', 'Read audit logs', 'View audit and login logs')
ON DUPLICATE KEY UPDATE
    permission_name = VALUES(permission_name),
    description = VALUES(description);

DELETE rp
FROM role_permissions rp
JOIN roles r ON r.role_id = rp.role_id
JOIN permissions p ON p.permission_id = rp.permission_id
WHERE p.permission_code = 'user.read'
  AND r.role_code IN ('learner', 'educator');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p ON
    (r.role_code = 'learner' AND p.permission_code IN (
        'course.enrol',
        'forum.read',
        'forum.write',
        'notification.read',
        'ai.chat.use',
        'learner_profile.manage',
        'quiz.attempt'
    ))
    OR (r.role_code = 'educator' AND p.permission_code IN (
        'course.create',
        'course.update',
        'course.publish',
        'course_enrollment.manage',
        'resource.upload',
        'resource.manage',
        'learning_path.create',
        'learning_path.update',
        'learning_path.delete',
        'learning_path.manage',
        'module.create',
        'module.update',
        'module.delete',
        'module.publish',
        'forum.read',
        'forum.write',
        'forum.pin',
        'notification.read',
        'ai.chat.use'
    ))
    OR (r.role_code = 'admin' AND p.permission_code IN (
        'user.read',
        'user.update',
        'user.activate',
        'user.deactivate',
        'educator_approval.read',
        'educator_approval.review',
        'role.assign',
        'course.update',
        'course.publish',
        'course.enrol',
        'course_enrollment.manage',
        'resource.upload',
        'resource.manage',
        'learning_path.create',
        'learning_path.update',
        'learning_path.delete',
        'learning_path.manage',
        'module.create',
        'module.update',
        'module.delete',
        'module.publish',
        'forum.read',
        'forum.write',
        'forum.pin',
        'notification.read',
        'notification.manage',
        'ai.governance.manage',
        'audit_log.read'
    ))
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);

CREATE TABLE IF NOT EXISTS educator_invite_tokens (
    invite_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    invite_uuid VARCHAR(36) NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    created_by_user_id BIGINT NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    used_by_user_id BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_educator_invite_tokens_uuid UNIQUE (invite_uuid),
    CONSTRAINT uq_educator_invite_tokens_hash UNIQUE (token_hash),
    CONSTRAINT fk_educator_invite_tokens_creator FOREIGN KEY (created_by_user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_educator_invite_tokens_used_by FOREIGN KEY (used_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL
) COMMENT='One-time educator invite tokens generated by admins for direct educator registration.';
