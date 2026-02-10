set -euo pipefail

az extension add --name rdbms-connect --upgrade --only-show-errors >/dev/null 2>&1 || true

POSTGRESQL_TOKEN="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"

run_sql_with_retry() {
  local database_name="$1"
  local sql_text="$2"
  local max_attempts=20
  local wait_seconds=15
  local attempt=1

  while true; do
    if az postgres flexible-server execute \
      --name "$POSTGRESQL_SERVER_NAME" \
      --admin-user "$POSTGRESQL_ENTRA_BOOTSTRAP_ADMIN_LOGIN" \
      --admin-password "$POSTGRESQL_TOKEN" \
      --database-name "$database_name" \
      --querytext "$sql_text" \
      --only-show-errors \
      --output none; then
      return 0
    fi

    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "SQL execution failed after $max_attempts attempts." >&2
      return 1
    fi

    echo "SQL execution attempt $attempt/$max_attempts failed; retrying in $wait_seconds seconds..."
    sleep "$wait_seconds"
    attempt=$((attempt + 1))
    POSTGRESQL_TOKEN="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"
  done
}

run_sql_with_retry_for_database() {
  local database_name="$1"
  local sql_text="$2"
  run_sql_with_retry "$database_name" "$sql_text"
}

create_service_principal_role_if_missing() {
  local role_name="$1"
  local object_id="$2"
  local sql_text

  sql_text="DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$role_name') THEN PERFORM pg_catalog.pgaadauth_create_principal_with_oid('$role_name', '$object_id', 'service', false, false); END IF; END \$\$;"
  run_sql_with_retry postgres "$sql_text"
}

create_group_role_if_missing() {
  local role_name="$1"
  local object_id="$2"
  local sql_text

  sql_text="DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$role_name') THEN PERFORM pg_catalog.pgaadauth_create_principal_with_oid('$role_name', '$object_id', 'group', false, false); END IF; END \$\$;"
  run_sql_with_retry postgres "$sql_text"
}

grant_database_access_to_app_role() {
  local database_name="$1"
  local role_name="$2"
  local sql_text

  sql_text="GRANT CONNECT, CREATE, TEMP ON DATABASE \"$database_name\" TO \"$role_name\";"
  run_sql_with_retry postgres "$sql_text"
}

apply_database_group_grants() {
  local database_name="$1"

  run_sql_with_retry postgres "GRANT CONNECT, TEMP ON DATABASE \"$database_name\" TO \"$DATABASE_READWRITE_ROLE_NAME\";"
  run_sql_with_retry postgres "GRANT CONNECT ON DATABASE \"$database_name\" TO \"$DATABASE_READONLY_ROLE_NAME\";"

  run_sql_with_retry_for_database "$database_name" "GRANT USAGE, CREATE ON SCHEMA public TO \"$DATABASE_READWRITE_ROLE_NAME\";"
  run_sql_with_retry_for_database "$database_name" "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"$DATABASE_READWRITE_ROLE_NAME\";"
  run_sql_with_retry_for_database "$database_name" "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO \"$DATABASE_READWRITE_ROLE_NAME\";"

  run_sql_with_retry_for_database "$database_name" "GRANT USAGE ON SCHEMA public TO \"$DATABASE_READONLY_ROLE_NAME\";"
  run_sql_with_retry_for_database "$database_name" "GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"$DATABASE_READONLY_ROLE_NAME\";"
  run_sql_with_retry_for_database "$database_name" "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO \"$DATABASE_READONLY_ROLE_NAME\";"
}

for required_environment_variable in \
  POSTGRESQL_SERVER_NAME \
  POSTGRESQL_ENTRA_BOOTSTRAP_ADMIN_LOGIN \
  PRODUCTION_CONTAINER_APP_ROLE_NAME \
  PRODUCTION_CONTAINER_APP_OBJECT_ID \
  PRODUCTION_DATABASE_NAME; do
  if [ -z "${!required_environment_variable:-}" ]; then
    echo "Missing required environment variable: $required_environment_variable" >&2
    exit 1
  fi
done

create_service_principal_role_if_missing "$PRODUCTION_CONTAINER_APP_ROLE_NAME" "$PRODUCTION_CONTAINER_APP_OBJECT_ID"
grant_database_access_to_app_role "$PRODUCTION_DATABASE_NAME" "$PRODUCTION_CONTAINER_APP_ROLE_NAME"

if [ "${DEPLOY_DEVELOPMENT_ENVIRONMENT:-false}" = "true" ]; then
  for required_development_variable in \
    DEVELOPMENT_CONTAINER_APP_ROLE_NAME \
    DEVELOPMENT_CONTAINER_APP_OBJECT_ID \
    DEVELOPMENT_DATABASE_NAME; do
    if [ -z "${!required_development_variable:-}" ]; then
      echo "Missing required development environment variable: $required_development_variable" >&2
      exit 1
    fi
  done

  create_service_principal_role_if_missing "$DEVELOPMENT_CONTAINER_APP_ROLE_NAME" "$DEVELOPMENT_CONTAINER_APP_OBJECT_ID"
  grant_database_access_to_app_role "$DEVELOPMENT_DATABASE_NAME" "$DEVELOPMENT_CONTAINER_APP_ROLE_NAME"
fi

if [ "${APPLY_DATABASE_GROUP_GRANTS:-false}" = "true" ]; then
  for required_group_variable in \
    DATABASE_READWRITE_ROLE_NAME \
    DATABASE_READWRITE_OBJECT_ID \
    DATABASE_READONLY_ROLE_NAME \
    DATABASE_READONLY_OBJECT_ID; do
    if [ -z "${!required_group_variable:-}" ]; then
      echo "Missing required database group grants variable: $required_group_variable" >&2
      exit 1
    fi
  done

  create_group_role_if_missing "$DATABASE_READWRITE_ROLE_NAME" "$DATABASE_READWRITE_OBJECT_ID"
  create_group_role_if_missing "$DATABASE_READONLY_ROLE_NAME" "$DATABASE_READONLY_OBJECT_ID"

  apply_database_group_grants "$PRODUCTION_DATABASE_NAME"

  if [ "${DEPLOY_DEVELOPMENT_ENVIRONMENT:-false}" = "true" ]; then
    apply_database_group_grants "$DEVELOPMENT_DATABASE_NAME"
  fi
fi

echo "{\"productionContainerAppRole\":\"$PRODUCTION_CONTAINER_APP_ROLE_NAME\",\"deployDevelopmentEnvironment\":\"${DEPLOY_DEVELOPMENT_ENVIRONMENT:-false}\"}" > "$AZ_SCRIPTS_OUTPUT_PATH"
