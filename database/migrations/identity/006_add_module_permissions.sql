INSERT INTO permissions (permission_code, permission_name, description)
VALUES
    ('module.create', 'Create module', 'Create course modules'),
    ('module.update', 'Update module', 'Update course modules'),
    ('module.delete', 'Delete module', 'Delete course modules'),
    ('module.publish', 'Publish module', 'Publish or change module visibility')
ON DUPLICATE KEY UPDATE
    permission_name = VALUES(permission_name),
    description = VALUES(description);

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p ON p.permission_code IN (
    'module.create',
    'module.update',
    'module.delete',
    'module.publish'
)
WHERE r.role_code IN ('educator', 'admin')
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);
