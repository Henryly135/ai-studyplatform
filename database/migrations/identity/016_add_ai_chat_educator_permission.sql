UPDATE permissions
SET
    permission_name = 'Use AI chat',
    description = 'Use AI chat features'
WHERE permission_code = 'ai.chat.use';

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p
  ON r.role_code = 'educator'
 AND p.permission_code = 'ai.chat.use'
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);
