INSERT INTO users (
    email,
    password_hash,
    full_name,
    account_status,
    email_verified
)
VALUES (
    'admin@example.com',
    'df88c832e9ed606645d98fac326669b3e12856e23719aabdfd7d894212ec1a0b',
    'Demo Admin',
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
WHERE u.email = 'admin@example.com'
ON DUPLICATE KEY UPDATE
    user_id = VALUES(user_id),
    role_id = VALUES(role_id);
