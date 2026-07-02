INSERT INTO users (
    email,
    password_hash,
    full_name,
    account_status,
    email_verified
)
VALUES (
    'Educator@gmail.com',
    'pbkdf2_sha256$600000$Ym9vdHN0cmFwLWVkdWNhdG9yLXYx$SVlKtRSDTm/5/2d3Kwwjq6N3042exx7vG2eZPLkrwGA=',
    'System Educator',
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
JOIN roles r ON r.role_code = 'educator'
WHERE u.email = 'Educator@gmail.com'
ON DUPLICATE KEY UPDATE
    user_id = VALUES(user_id),
    role_id = VALUES(role_id);
