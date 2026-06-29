INSERT INTO users (
    email,
    password_hash,
    full_name,
    account_status,
    email_verified
)
VALUES (
    'eduplatform.aibot@gmail.com',
    '5785264f6d90120c8f35637046e34725c7ad048547f3665392a745283d8fd528',
    'Edu Platform Admin',
    'active',
    TRUE
)
ON DUPLICATE KEY UPDATE
    password_hash = VALUES(password_hash),
    full_name = VALUES(full_name),
    account_status = VALUES(account_status),
    email_verified = VALUES(email_verified);

INSERT INTO user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r ON r.role_code = 'admin'
WHERE u.email = 'eduplatform.aibot@gmail.com'
ON DUPLICATE KEY UPDATE
    user_id = VALUES(user_id),
    role_id = VALUES(role_id);
