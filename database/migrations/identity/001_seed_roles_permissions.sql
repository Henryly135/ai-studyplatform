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
    ('resource.upload', 'Upload resources', 'Upload learning resources'),
    ('resource.manage', 'Manage resources', 'Manage uploaded learning resources'),
    ('learning_path.create', 'Create learning path', 'Create learning paths'),
    ('learning_path.update', 'Update learning path', 'Update learning paths'),
    ('learning_path.delete', 'Delete learning path', 'Delete learning paths'),
    ('learning_path.manage', 'Manage learning path', 'Manage learning paths end-to-end'),
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
    (r.role_code = 'educator' AND p.permission_code IN (
        'course.create',
        'resource.upload',
        'resource.manage',
        'learning_path.create',
        'learning_path.update',
        'learning_path.delete',
        'learning_path.manage'
    ))
    OR (r.role_code = 'admin' AND p.permission_code IN (
        'user.read',
        'user.update',
        'user.activate',
        'user.deactivate',
        'educator_approval.read',
        'educator_approval.review',
        'role.assign',
        'course.create',
        'resource.upload',
        'resource.manage',
        'learning_path.create',
        'learning_path.update',
        'learning_path.delete',
        'learning_path.manage',
        'audit_log.read'
    ))
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);
