INSERT INTO permissions (permission_code, permission_name, description)
VALUES
    ('course_enrollment.manage', 'Manage course enrollment', 'Manage learner enrollment status for courses')
ON DUPLICATE KEY UPDATE
    permission_name = VALUES(permission_name),
    description = VALUES(description);

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p ON p.permission_code = 'course_enrollment.manage'
WHERE r.role_code IN ('educator', 'admin')
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);
