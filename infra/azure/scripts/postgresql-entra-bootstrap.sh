#!/usr/bin/env bash
set -euo pipefail

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name" >&2
    exit 1
  fi
}

require_command az
require_command psql

require_env() {
  local variable_name="$1"
  if [ -z "${!variable_name:-}" ]; then
    echo "Missing required environment variable: $variable_name" >&2
    exit 1
  fi
}

require_env POSTGRESQL_SERVER_FQDN
require_env POSTGRESQL_ENTRA_BOOTSTRAP_LOGIN
require_env PRODUCTION_CONTAINER_APP_ROLE_NAME
require_env PRODUCTION_CONTAINER_APP_OBJECT_ID
require_env PRODUCTION_DATABASE_NAME

DEPLOY_DEVELOPMENT_ENVIRONMENT="${DEPLOY_DEVELOPMENT_ENVIRONMENT:-false}"

if [ "$DEPLOY_DEVELOPMENT_ENVIRONMENT" = "true" ]; then
  require_env DEVELOPMENT_CONTAINER_APP_ROLE_NAME
  require_env DEVELOPMENT_CONTAINER_APP_OBJECT_ID
  require_env DEVELOPMENT_DATABASE_NAME
fi

require_env DATABASE_READWRITE_ROLE_NAME
require_env DATABASE_READWRITE_OBJECT_ID
require_env DATABASE_READONLY_ROLE_NAME
require_env DATABASE_READONLY_OBJECT_ID

refresh_postgresql_token() {
  POSTGRESQL_TOKEN="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"
}

run_sql_with_retry() {
  local database_name="$1"
  local sql_text="$2"
  local max_attempts=20
  local wait_seconds=15
  local attempt=1

  refresh_postgresql_token

  while true; do
    if PGPASSWORD="$POSTGRESQL_TOKEN" \
      PGCONNECT_TIMEOUT=15 \
      psql \
        "host=${POSTGRESQL_SERVER_FQDN} port=5432 dbname=${database_name} user=${POSTGRESQL_ENTRA_BOOTSTRAP_LOGIN} sslmode=require" \
        --set ON_ERROR_STOP=on \
        --quiet \
        --command "$sql_text" >/dev/null; then
      return 0
    fi

    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "SQL execution failed after $max_attempts attempts for database '${database_name}'." >&2
      return 1
    fi

    echo "SQL execution attempt $attempt/$max_attempts failed for database '${database_name}'; retrying in $wait_seconds seconds..."
    sleep "$wait_seconds"
    attempt=$((attempt + 1))
    refresh_postgresql_token
  done
}

create_principal_role_if_missing() {
  local role_name="$1"
  local object_id="$2"
  local principal_type="$3"
  local sql_text

  sql_text="DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$role_name') THEN PERFORM pg_catalog.pgaadauth_create_principal_with_oid('$role_name', '$object_id', '$principal_type', false, false); END IF; END \$\$;"
  run_sql_with_retry postgres "$sql_text"
}

apply_app_role_grants() {
  local database_name="$1"
  local role_name="$2"

  run_sql_with_retry postgres "GRANT CONNECT, CREATE, TEMP ON DATABASE \"$database_name\" TO \"$role_name\";"
  run_sql_with_retry "$database_name" "GRANT USAGE, CREATE ON SCHEMA public TO \"$role_name\";"
  run_sql_with_retry "$database_name" "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"$role_name\";"
  run_sql_with_retry "$database_name" "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO \"$role_name\";"
}

apply_database_group_grants() {
  local database_name="$1"

  run_sql_with_retry postgres "GRANT CONNECT, TEMP ON DATABASE \"$database_name\" TO \"$DATABASE_READWRITE_ROLE_NAME\";"
  run_sql_with_retry postgres "GRANT CONNECT ON DATABASE \"$database_name\" TO \"$DATABASE_READONLY_ROLE_NAME\";"

  run_sql_with_retry "$database_name" "GRANT USAGE, CREATE ON SCHEMA public TO \"$DATABASE_READWRITE_ROLE_NAME\";"
  run_sql_with_retry "$database_name" "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"$DATABASE_READWRITE_ROLE_NAME\";"
  run_sql_with_retry "$database_name" "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO \"$DATABASE_READWRITE_ROLE_NAME\";"

  run_sql_with_retry "$database_name" "GRANT USAGE ON SCHEMA public TO \"$DATABASE_READONLY_ROLE_NAME\";"
  run_sql_with_retry "$database_name" "GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"$DATABASE_READONLY_ROLE_NAME\";"
  run_sql_with_retry "$database_name" "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO \"$DATABASE_READONLY_ROLE_NAME\";"
}

echo "Bootstrapping PostgreSQL Entra principals and grants..."

create_principal_role_if_missing "$PRODUCTION_CONTAINER_APP_ROLE_NAME" "$PRODUCTION_CONTAINER_APP_OBJECT_ID" "service"
apply_app_role_grants "$PRODUCTION_DATABASE_NAME" "$PRODUCTION_CONTAINER_APP_ROLE_NAME"

if [ "$DEPLOY_DEVELOPMENT_ENVIRONMENT" = "true" ]; then
  create_principal_role_if_missing "$DEVELOPMENT_CONTAINER_APP_ROLE_NAME" "$DEVELOPMENT_CONTAINER_APP_OBJECT_ID" "service"
  apply_app_role_grants "$DEVELOPMENT_DATABASE_NAME" "$DEVELOPMENT_CONTAINER_APP_ROLE_NAME"
fi

create_principal_role_if_missing "$DATABASE_READWRITE_ROLE_NAME" "$DATABASE_READWRITE_OBJECT_ID" "group"
create_principal_role_if_missing "$DATABASE_READONLY_ROLE_NAME" "$DATABASE_READONLY_OBJECT_ID" "group"

apply_database_group_grants "$PRODUCTION_DATABASE_NAME"

if [ "$DEPLOY_DEVELOPMENT_ENVIRONMENT" = "true" ]; then
  apply_database_group_grants "$DEVELOPMENT_DATABASE_NAME"
fi

echo "PostgreSQL Entra bootstrap completed."
