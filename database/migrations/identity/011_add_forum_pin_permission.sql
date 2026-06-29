INSERT INTO permissions (permission_code, permission_name, description)
VALUES
    ('forum.pin', 'Pin forum posts', 'Pin and unpin forum posts for courses you moderate')
ON DUPLICATE KEY UPDATE
    permission_name = VALUES(permission_name),
    description = VALUES(description);

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p ON
    (r.role_code = 'educator' AND p.permission_code = 'forum.pin')
    OR (r.role_code = 'admin' AND p.permission_code = 'forum.pin')
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);
