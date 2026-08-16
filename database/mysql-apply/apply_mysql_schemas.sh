#!/bin/sh
set -eu

MYSQL_HOST="${MYSQL_HOST:-mysql}"
MYSQL_PORT="${MYSQL_INTERNAL_PORT:-3306}"
DEFAULT_ADMIN_EMAIL="${DEFAULT_ADMIN_EMAIL:-eduplatform.aibot@gmail.com}"
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-Eduadmin123!}"
DEFAULT_ADMIN_FULL_NAME="${DEFAULT_ADMIN_FULL_NAME:-Edu Platform Admin}"
LOCAL_DEMO_SINGLE_ACCOUNT_ENABLED="${LOCAL_DEMO_SINGLE_ACCOUNT_ENABLED:-false}"
PASSWORD_HASH_ITERATIONS="${PASSWORD_HASH_ITERATIONS:-600000}"

is_production_env() {
  app_env="$(printf "%s" "${APP_ENV:-local}" | tr '[:upper:]' '[:lower:]')"
  [ "${app_env}" = "prod" ] || [ "${app_env}" = "production" ]
}

is_local_demo_single_account_enabled() {
  enabled="$(printf "%s" "${LOCAL_DEMO_SINGLE_ACCOUNT_ENABLED}" | tr '[:upper:]' '[:lower:]')"
  [ "${enabled}" = "true" ] || [ "${enabled}" = "1" ] || [ "${enabled}" = "yes" ]
}

validate_production_bootstrap_config() {
  if ! is_production_env; then
    return 0
  fi

  case "${DEFAULT_ADMIN_EMAIL}" in
    ""|"admin@gmail.com"|"eduplatform.aibot@gmail.com"|"demo@example.com"|"your.team.email@gmail.com")
      echo "DEFAULT_ADMIN_EMAIL must be changed from the demo/default value in production." >&2
      exit 1
      ;;
  esac

  case "${DEFAULT_ADMIN_PASSWORD}" in
    ""|"Eduadmin123!"|"LocalDemo123!"|"your-admin-password"|"password"|"secret")
      echo "DEFAULT_ADMIN_PASSWORD must be changed from the demo/default value in production." >&2
      exit 1
      ;;
  esac

  if [ "${#DEFAULT_ADMIN_PASSWORD}" -lt 16 ]; then
    echo "DEFAULT_ADMIN_PASSWORD must be at least 16 characters in production." >&2
    exit 1
  fi

  if is_local_demo_single_account_enabled; then
    echo "LOCAL_DEMO_SINGLE_ACCOUNT_ENABLED must be false in production." >&2
    exit 1
  fi
}

mysql_root() {
  mysql -h"${MYSQL_HOST}" -P"${MYSQL_PORT}" -uroot -p"${MYSQL_ROOT_PASSWORD}" "$@"
}

sql_escape() {
  printf "%s" "$1" | sed "s/'/''/g"
}

generate_pbkdf2_password_hash() {
  password="$1"
  salt_value="$(openssl rand -hex 16)"
  salt_b64="$(printf "%s" "${salt_value}" | base64 | tr -d '\n')"
  hash_b64="$(openssl kdf \
    -keylen 32 \
    -binary \
    -kdfopt digest:SHA256 \
    -kdfopt "pass:${password}" \
    -kdfopt "salt:${salt_value}" \
    -kdfopt "iter:${PASSWORD_HASH_ITERATIONS}" \
    PBKDF2 | base64 | tr -d '\n')"

  printf "pbkdf2_sha256$%s$%s$%s" "${PASSWORD_HASH_ITERATIONS}" "${salt_b64}" "${hash_b64}"
}

wait_for_mysql() {
  attempt=1
  max_attempts=30

  while [ "${attempt}" -le "${max_attempts}" ]; do
    if mysql_root -e "SELECT 1" >/dev/null 2>&1; then
      return 0
    fi

    echo "Waiting for MySQL bootstrap to finish (${attempt}/${max_attempts})..."
    sleep 2
    attempt=$((attempt + 1))
  done

  echo "MySQL did not become ready for schema apply in time." >&2
  return 1
}

ensure_migration_table() {
  db_name="$1"

  mysql_root "${db_name}" <<'EOSQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name VARCHAR(255) PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
EOSQL
}

column_exists() {
  db_name="$1"
  table_name="$2"
  column_name="$3"

  exists_count="$(mysql_root -N -B -e "
    SELECT COUNT(1)
    FROM information_schema.columns
    WHERE table_schema = '${db_name}'
      AND table_name = '${table_name}'
      AND column_name = '${column_name}'
  ")"

  [ "${exists_count}" != "0" ]
}

mark_migration_applied() {
  db_name="$1"
  migration_name="$2"

  mysql_root "${db_name}" -e "
    INSERT INTO schema_migrations (migration_name)
    VALUES ('${migration_name}')
    ON DUPLICATE KEY UPDATE migration_name = VALUES(migration_name);
  "
}

is_migration_applied() {
  db_name="$1"
  migration_name="$2"

  applied_count="$(mysql_root "${db_name}" -N -B -e "
    SELECT COUNT(1)
    FROM schema_migrations
    WHERE migration_name = '${migration_name}'
  ")"

  [ "${applied_count}" != "0" ]
}

seed_baseline_migrations() {
  db_name="$1"
  shift

  for migration_name in "$@"; do
    mark_migration_applied "${db_name}" "${migration_name}"
  done
}

seed_communication_baseline_migrations() {
  db_name="$1"

  # Fresh databases are created from schema.communication.sql, which already
  # includes the forum pin columns. Mark the matching migration as applied only
  # when that schema state is already present. Existing databases without the
  # new columns will still run the migration below.
  if column_exists "${db_name}" "course_forum_posts" "is_pinned"; then
    mark_migration_applied "${db_name}" "001_add_forum_post_pin_columns.sql"
  fi
}

seed_default_admin_account() {
  db_name="$1"
  admin_email="$(sql_escape "${DEFAULT_ADMIN_EMAIL}")"
  admin_password_hash="$(sql_escape "$(generate_pbkdf2_password_hash "${DEFAULT_ADMIN_PASSWORD}")")"
  admin_full_name="$(sql_escape "${DEFAULT_ADMIN_FULL_NAME}")"

  mysql_root "${db_name}" <<EOSQL
UPDATE users
SET
    email = '${admin_email}',
    password_hash = '${admin_password_hash}',
    full_name = '${admin_full_name}',
    account_status = 'active',
    email_verified = TRUE
WHERE email = 'admin@gmail.com'
  AND NOT EXISTS (
    SELECT 1
    FROM (SELECT user_id FROM users WHERE email = '${admin_email}') existing_admin
  );

INSERT INTO users (
    email,
    password_hash,
    full_name,
    account_status,
    email_verified
)
VALUES (
    '${admin_email}',
    '${admin_password_hash}',
    '${admin_full_name}',
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
WHERE u.email = '${admin_email}'
ON DUPLICATE KEY UPDATE
    user_id = VALUES(user_id),
    role_id = VALUES(role_id);
EOSQL

  if is_local_demo_single_account_enabled; then
    mysql_root "${db_name}" <<EOSQL
INSERT INTO user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM users u
JOIN roles r ON r.role_code IN ('learner', 'educator', 'admin')
WHERE u.email = '${admin_email}'
ON DUPLICATE KEY UPDATE
    user_id = VALUES(user_id),
    role_id = VALUES(role_id);
EOSQL
  fi
}

apply_pending_migrations() {
  db_name="$1"
  migration_dir="$2"

  for migration_path in "${migration_dir}"/*.sql; do
    [ -f "${migration_path}" ] || continue

    migration_name="$(basename "${migration_path}")"
    if is_migration_applied "${db_name}" "${migration_name}"; then
      continue
    fi

    echo "Applying migration ${db_name}/${migration_name}"
    mysql_root "${db_name}" < "${migration_path}"
    mark_migration_applied "${db_name}" "${migration_name}"
  done
}

ensure_index() {
  db_name="$1"
  table_name="$2"
  index_name="$3"
  columns_sql="$4"

  exists_count="$(mysql_root -N -B -e "
    SELECT COUNT(1)
    FROM information_schema.statistics
    WHERE table_schema = '${db_name}'
      AND table_name = '${table_name}'
      AND index_name = '${index_name}'
  ")"

  if [ "${exists_count}" = "0" ]; then
    mysql_root "${db_name}" -e "CREATE INDEX ${index_name} ON ${table_name} ${columns_sql};"
  fi
}

validate_production_bootstrap_config
wait_for_mysql

mysql_root <<-EOSQL
  CREATE DATABASE IF NOT EXISTS \`${IDENTITY_DB_NAME}\`;
  CREATE DATABASE IF NOT EXISTS \`${COMMUNICATION_DB_NAME}\`;
  CREATE DATABASE IF NOT EXISTS \`${LEARNING_DB_NAME}\`;

  CREATE USER IF NOT EXISTS '${IDENTITY_DB_USER}'@'%' IDENTIFIED BY '${IDENTITY_DB_PASSWORD}';
  CREATE USER IF NOT EXISTS '${COMMUNICATION_DB_USER}'@'%' IDENTIFIED BY '${COMMUNICATION_DB_PASSWORD}';
  CREATE USER IF NOT EXISTS '${LEARNING_DB_USER}'@'%' IDENTIFIED BY '${LEARNING_DB_PASSWORD}';
  CREATE USER IF NOT EXISTS '${MYSQL_SHARED_USER}'@'%' IDENTIFIED BY '${MYSQL_SHARED_PASSWORD}';

  GRANT ALL PRIVILEGES ON \`${IDENTITY_DB_NAME}\`.* TO '${IDENTITY_DB_USER}'@'%';
  GRANT ALL PRIVILEGES ON \`${COMMUNICATION_DB_NAME}\`.* TO '${COMMUNICATION_DB_USER}'@'%';
  GRANT ALL PRIVILEGES ON \`${LEARNING_DB_NAME}\`.* TO '${LEARNING_DB_USER}'@'%';
  GRANT ALL PRIVILEGES ON \`${IDENTITY_DB_NAME}\`.* TO '${MYSQL_SHARED_USER}'@'%';
  GRANT ALL PRIVILEGES ON \`${COMMUNICATION_DB_NAME}\`.* TO '${MYSQL_SHARED_USER}'@'%';
  GRANT ALL PRIVILEGES ON \`${LEARNING_DB_NAME}\`.* TO '${MYSQL_SHARED_USER}'@'%';
  FLUSH PRIVILEGES;
EOSQL

mysql_root "${IDENTITY_DB_NAME}" < /bootstrap/schema.identity.sql
mysql_root "${COMMUNICATION_DB_NAME}" < /bootstrap/schema.communication.sql
mysql_root "${LEARNING_DB_NAME}" < /bootstrap/schema.learning.sql

ensure_migration_table "${IDENTITY_DB_NAME}"
ensure_migration_table "${COMMUNICATION_DB_NAME}"
ensure_migration_table "${LEARNING_DB_NAME}"

# The schema files represent the current baseline. We mark the historical
# migrations already reflected there so future restarts only execute newer files.
seed_baseline_migrations "${IDENTITY_DB_NAME}" \
  "001_seed_roles_permissions.sql" \
  "002_add_course_create_permission.sql" \
  "003_restrict_user_read_to_admin.sql" \
  "004_add_course_enrol_permission.sql" \
  "005_add_course_enrollment_manage_permission.sql" \
  "006_add_module_permissions.sql" \
  "007_add_course_publish_permission.sql" \
  "008_add_course_update_permission.sql" \
  "009_remove_admin_course_create_permission.sql" \
  "010_add_communication_permissions.sql" \
  "012_seed_default_admin_account.sql" \
  "013_seed_default_educator_account.sql" \
  "014_add_ai_chat_and_learner_profile_permissions.sql" \
  "015_add_ai_governance_manage_permission.sql"

seed_default_admin_account "${IDENTITY_DB_NAME}"

seed_baseline_migrations "${LEARNING_DB_NAME}" \
  "001_add_course_enrollment_audit_logs.sql" \
  "002_add_module_authoring_fields.sql" \
  "003_add_module_prerequisites.sql" \
  "004_rename_module_visibility_to_status.sql" \
  "005_add_module_material_upload_sessions.sql" \
  "006_add_quiz_tables.sql" \
  "007_drop_quiz_attempt_sessions_table.sql"

seed_communication_baseline_migrations "${COMMUNICATION_DB_NAME}"

apply_pending_migrations "${IDENTITY_DB_NAME}" "/bootstrap/migrations/identity"
apply_pending_migrations "${COMMUNICATION_DB_NAME}" "/bootstrap/migrations/communication"
apply_pending_migrations "${LEARNING_DB_NAME}" "/bootstrap/migrations/learning"

ensure_index "${IDENTITY_DB_NAME}" "users" "idx_users_account_status" "(account_status)"
ensure_index "${IDENTITY_DB_NAME}" "user_roles" "idx_user_roles_role_id" "(role_id)"
ensure_index "${IDENTITY_DB_NAME}" "role_permissions" "idx_role_permissions_permission_id" "(permission_id)"
ensure_index "${IDENTITY_DB_NAME}" "educator_approval_requests" "idx_educator_approval_requests_user_id" "(user_id)"
ensure_index "${IDENTITY_DB_NAME}" "educator_approval_requests" "idx_educator_approval_requests_status" "(request_status)"
ensure_index "${IDENTITY_DB_NAME}" "email_verification_tokens" "idx_email_verification_tokens_user_id" "(user_id)"
ensure_index "${IDENTITY_DB_NAME}" "email_verification_tokens" "idx_email_verification_tokens_expires_at" "(expires_at)"
ensure_index "${IDENTITY_DB_NAME}" "password_reset_tokens" "idx_password_reset_tokens_user_id" "(user_id)"
ensure_index "${IDENTITY_DB_NAME}" "password_reset_tokens" "idx_password_reset_tokens_expires_at" "(expires_at)"
ensure_index "${IDENTITY_DB_NAME}" "user_role_audit_logs" "idx_user_role_audit_logs_target_user_id" "(target_user_id)"
ensure_index "${IDENTITY_DB_NAME}" "user_role_audit_logs" "idx_user_role_audit_logs_changed_by" "(changed_by)"
ensure_index "${IDENTITY_DB_NAME}" "user_role_audit_logs" "idx_user_role_audit_logs_change_type" "(change_type)"
ensure_index "${IDENTITY_DB_NAME}" "login_audit_logs" "idx_login_audit_logs_user_id" "(user_id)"
ensure_index "${IDENTITY_DB_NAME}" "login_audit_logs" "idx_login_audit_logs_email_attempted" "(email_attempted)"
ensure_index "${IDENTITY_DB_NAME}" "login_audit_logs" "idx_login_audit_logs_login_result" "(login_result)"
ensure_index "${IDENTITY_DB_NAME}" "login_audit_logs" "idx_login_audit_logs_created_at" "(created_at)"

ensure_index "${LEARNING_DB_NAME}" "courses" "idx_courses_educator_id" "(educator_id)"
ensure_index "${LEARNING_DB_NAME}" "courses" "idx_courses_status" "(status)"
ensure_index "${LEARNING_DB_NAME}" "courses" "idx_courses_category" "(category)"
ensure_index "${LEARNING_DB_NAME}" "modules" "idx_modules_learning_path_id" "(learning_path_id)"
ensure_index "${LEARNING_DB_NAME}" "module_materials" "idx_module_materials_module_id" "(module_id)"
ensure_index "${LEARNING_DB_NAME}" "course_enrollments" "idx_course_enrollments_learner_id" "(learner_id)"
ensure_index "${LEARNING_DB_NAME}" "course_enrollments" "idx_course_enrollments_status" "(enrollment_status)"
ensure_index "${LEARNING_DB_NAME}" "course_enrollment_audit_logs" "idx_course_enrollment_audit_logs_enrollment_id" "(enrollment_id)"
ensure_index "${LEARNING_DB_NAME}" "course_enrollment_audit_logs" "idx_course_enrollment_audit_logs_course_id" "(course_id)"
ensure_index "${LEARNING_DB_NAME}" "course_enrollment_audit_logs" "idx_course_enrollment_audit_logs_learner_id" "(learner_id)"
ensure_index "${LEARNING_DB_NAME}" "course_enrollment_audit_logs" "idx_course_enrollment_audit_logs_created_at" "(created_at)"
ensure_index "${LEARNING_DB_NAME}" "module_progress" "idx_module_progress_learner_id" "(learner_id)"
ensure_index "${LEARNING_DB_NAME}" "module_progress" "idx_module_progress_status" "(progress_status)"
ensure_index "${LEARNING_DB_NAME}" "quizzes" "idx_quizzes_status" "(status)"
ensure_index "${LEARNING_DB_NAME}" "quiz_questions" "idx_quiz_questions_quiz_active" "(quiz_id, is_active)"
ensure_index "${LEARNING_DB_NAME}" "quiz_question_options" "idx_quiz_question_options_question_id" "(quiz_question_id)"
ensure_index "${LEARNING_DB_NAME}" "quiz_attempts" "idx_quiz_attempts_quiz_learner_created_at" "(quiz_id, learner_id, created_at)"
ensure_index "${LEARNING_DB_NAME}" "quiz_attempts" "idx_quiz_attempts_module_learner_passed" "(module_id, learner_id, is_passed)"
ensure_index "${LEARNING_DB_NAME}" "quiz_attempts" "idx_quiz_attempts_learner_id" "(learner_id)"
ensure_index "${LEARNING_DB_NAME}" "quiz_attempt_answers" "idx_quiz_attempt_answers_attempt_order" "(quiz_attempt_id, question_order)"

ensure_index "${COMMUNICATION_DB_NAME}" "course_forum_posts" "idx_course_forum_posts_course_pinned_created" "(course_id, is_pinned, pinned_at, created_at, post_id)"
