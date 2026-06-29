INSERT INTO permissions (permission_code, permission_name, description)
VALUES
    ('course.enrol', 'Enrol course', 'Enrol in courses as a learner')
ON DUPLICATE KEY UPDATE
    permission_name = VALUES(permission_name),
    description = VALUES(description);

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p ON p.permission_code = 'course.enrol'
WHERE r.role_code IN ('learner', 'admin')
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);
