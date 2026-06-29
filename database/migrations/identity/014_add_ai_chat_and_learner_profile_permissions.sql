INSERT INTO permissions (permission_code, permission_name, description)
VALUES
    ('ai.chat.use', 'Use AI chat', 'Use learner-facing AI chatbot features'),
    ('learner_profile.manage', 'Manage learner profile', 'Create and view learner global profile settings'),
    ('quiz.attempt', 'Attempt quiz', 'Start and submit learner quiz attempts')
ON DUPLICATE KEY UPDATE
    permission_name = VALUES(permission_name),
    description = VALUES(description);

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
JOIN permissions p
  ON r.role_code = 'learner'
 AND p.permission_code IN ('ai.chat.use', 'learner_profile.manage', 'quiz.attempt')
ON DUPLICATE KEY UPDATE
    role_id = VALUES(role_id),
    permission_id = VALUES(permission_id);
