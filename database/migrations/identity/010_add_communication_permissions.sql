INSERT INTO permissions (permission_code, permission_name, description)
VALUES
    ('forum.read', 'Read forum', 'View course forum posts and comments'),
    ('forum.write', 'Write forum', 'Create and manage own course forum posts and comments'),
    ('notification.read', 'Read notifications', 'View and manage personal notifications'),
    ('notification.manage', 'Manage notifications', 'Create, update and delete system notifications')
ON DUPLICATE KEY UPDATE
    permission_name = VALUES(permission_name),
    description = VALUES(description);

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p ON
    (r.role_code = 'learner' AND p.permission_code IN ('forum.read', 'forum.write', 'notification.read'))
    OR (r.role_code = 'educator' AND p.permission_code IN ('forum.read', 'forum.write', 'notification.read'))
    OR (r.role_code = 'admin' AND p.permission_code IN ('forum.read', 'forum.write', 'notification.read', 'notification.manage'))
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);
