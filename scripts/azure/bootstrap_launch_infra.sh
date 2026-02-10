#!/usr/bin/env bash
set -euo pipefail

# Quick start (prod + dev):
#   Uses ./bootstrap_launch_infra.env and deploys full infrastructure + both apps.
#   bash scripts/azure/bootstrap_launch_infra.sh --env-file ./bootstrap_launch_infra.env
#
# Quick start (prod-only):
#   bash scripts/azure/bootstrap_launch_infra.sh --env-file ./bootstrap_launch_infra.env --deploy-dev false

log() {
  printf '[bootstrap] %s\n' "$*"
}

die() {
  printf '[bootstrap] error: %s\n' "$*" >&2
  exit 1
}

trim() {
  local value="${1:-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

normalize_bool() {
  local value
  value="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    true|1|yes|y|on) printf 'true' ;;
    false|0|no|n|off) printf 'false' ;;
    *)
      die "invalid boolean value: ${1:-<empty>} (expected true|false)"
      ;;
  esac
}

normalize_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

sanitize_dash_token() {
  local value="$1"
  value="$(normalize_lower "$value" | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"
  printf '%s' "$value"
}

sanitize_alnum_token() {
  local value="$1"
  value="$(normalize_lower "$value" | tr -cd 'a-z0-9')"
  printf '%s' "$value"
}

append_suffix_dash() {
  local base="$1"
  local suffix="$2"
  if [[ -z "$suffix" ]]; then
    printf '%s' "$base"
  else
    printf '%s-%s' "$base" "$suffix"
  fi
}

append_suffix_alnum() {
  local base="$1"
  local suffix="$2"
  printf '%s%s' "$base" "$suffix"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

require_non_empty() {
  local value="$1"
  local label="$2"
  if [[ -z "$value" ]]; then
    die "missing required value: $label"
  fi
}

is_cidr() {
  local value="$1"
  [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/([0-9]|[12][0-9]|3[0-2])$ ]]
}

validate_cidr_relationship() {
  local vnet_cidr="$1"
  local subnet_cidr="$2"
  if ! command -v python3 >/dev/null 2>&1; then
    [[ "$vnet_cidr" != "$subnet_cidr" ]] || die "VNet CIDR and subnet CIDR cannot be identical"
    return 0
  fi

  python3 - "$vnet_cidr" "$subnet_cidr" <<'PY'
import ipaddress
import sys

vnet = ipaddress.ip_network(sys.argv[1], strict=False)
subnet = ipaddress.ip_network(sys.argv[2], strict=False)
if not subnet.subnet_of(vnet):
    raise SystemExit(1)
PY
}

parse_postgres_version() {
  local version="$1"
  if [[ ! "$version" =~ ^([0-9]+)(\.([0-9]+))?$ ]]; then
    die "invalid POSTGRES_VERSION '${version}'. Expected 'major' (e.g. 18) or 'major.minor' (e.g. 18.1)."
  fi
  POSTGRES_VERSION_MAJOR="${BASH_REMATCH[1]}"
  if [[ -n "${BASH_REMATCH[3]:-}" ]]; then
    POSTGRES_VERSION_HAS_MINOR="true"
  else
    POSTGRES_VERSION_HAS_MINOR="false"
  fi
}

is_ipv4() {
  local value="$1"
  if [[ ! "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    return 1
  fi
  local o
  IFS='.' read -r -a octets <<<"$value"
  for o in "${octets[@]}"; do
    if (( o < 0 || o > 255 )); then
      return 1
    fi
  done
  return 0
}

yaml_quote() {
  local value="$1"
  value=${value//\'/\'\'}
  printf "'%s'" "$value"
}

sql_escape_literal() {
  printf "%s" "$1" | sed "s/'/''/g"
}

sql_escape_ident() {
  printf "%s" "$1" | sed 's/"/""/g'
}

load_env_file() {
  local path="$1"
  [[ -f "$path" ]] || die "env file not found: $path"
  # shellcheck disable=SC1090
  source "$path"
}

usage() {
  cat <<'EOF'
Bootstrap ADE launch infrastructure on Azure.

Usage:
  scripts/azure/bootstrap_launch_infra.sh [options]

Required options:
  --subscription-id <id>
  --location <region>
  --postgres-admin-user <name>
  --postgres-admin-password <password>
  --prod-image <image>
  --prod-web-url <url>
  --prod-secret-key <secret>

Optional:
  --env-file <path>
  --name-stem <token>                        (default: automaticdataextractor)
  --name-suffix <token>                      (default: none)
  --deploy-dev <bool>                        (default: true)
  --resource-group <name>                    (default: rg-<stem>[-<suffix>])
  --vnet-name <name>                         (default: vnet-<stem>[-<suffix>])
  --vnet-cidr <cidr>                         (default: 10.80.0.0/16)
  --aca-subnet-name <name>                   (default: snet-<stem>-aca[-<suffix>])
  --aca-subnet-cidr <cidr>                   (default: 10.80.0.0/23)
  --aca-env-name <name>                      (default: cae-<stem>-<location>[-<suffix>])
  --log-analytics-workspace-name <name>      (default: log-<stem>[-<suffix>])
  --postgres-server-name <name>              (default: psql-<stem>-<location>[-<suffix>])
  --postgres-prod-db <name>                  (default: ade)
  --postgres-dev-db <name>                   (default: ade_dev)
  --postgres-version <major[.minor]>         (default: 18.1)
  --postgres-tier <tier>                     (default: Burstable)
  --postgres-sku-name <sku>                  (default: Standard_B1ms)
  --postgres-storage-size-gb <int>           (default: 32)
  --storage-account-name <name>              (default: sa<stemnosymbols><suffixnosymbols>)
  --storage-sku <sku>                        (default: Standard_LRS)
  --prod-app-name <name>                     (default: ca-<stem>-prod[-<suffix>])
  --dev-app-name <name>                      (default: ca-<stem>-dev[-<suffix>], if --deploy-dev=true)
  --dev-image <image>                        (default: --prod-image)
  --dev-web-url <url>                        (required if --deploy-dev=true)
  --dev-secret-key <secret>                  (required if --deploy-dev=true)
  --blob-prod-container <name>               (default: ade-prod)
  --blob-dev-container <name>                (default: ade-dev, if --deploy-dev=true)
  --file-prod-share <name>                   (default: ade-data-prod)
  --file-dev-share <name>                    (default: ade-data-dev, if --deploy-dev=true)
  --prod-storage-mount-name <name>           (default: share-<stem>-prod[-<suffix>])
  --dev-storage-mount-name <name>            (default: share-<stem>-dev[-<suffix>], if --deploy-dev=true)
  --prod-db-role-name <name>                 (default: <prod-app-name>)
  --dev-db-role-name <name>                  (default: <dev-app-name>, if --deploy-dev=true)
  --database-auth-mode <mode>                (default: managed_identity; only this mode is supported)
  --enable-fabric-azure-services-rule <bool> (default: true)
  --operator-ip <ipv4>                       (repeatable)
  --operator-ips-csv <csv>                   (e.g. 203.0.113.10,198.51.100.20)
  --prod-min-replicas <int>                  (default: 1)
  --prod-max-replicas <int>                  (default: 2)
  --dev-min-replicas <int>                   (default: 0)
  --dev-max-replicas <int>                   (default: 1)
  --verify-deployment <bool>                 (default: true)
  --help

Notes:
  - This script intentionally does not create private endpoints.
  - PostgreSQL remains public for Fabric no-gateway mirroring and uses Entra auth for ADE runtime.
  - If POSTGRES_VERSION includes a minor (default 18.1), script enforces strict runtime match.

Quick start:
  cp scripts/azure/bootstrap_launch_infra.env.example ./bootstrap_launch_infra.env
  # edit values in ./bootstrap_launch_infra.env
  bash scripts/azure/bootstrap_launch_infra.sh --env-file ./bootstrap_launch_infra.env

  # Optional: prod-only
  bash scripts/azure/bootstrap_launch_infra.sh --env-file ./bootstrap_launch_infra.env --deploy-dev false
EOF
}

retry() {
  local attempts="$1"
  local wait_seconds="$2"
  shift 2
  local i
  for ((i=1; i<=attempts; i++)); do
    if "$@"; then
      return 0
    fi
    if (( i == attempts )); then
      return 1
    fi
    sleep "$wait_seconds"
  done
}

ensure_provider_registered() {
  local namespace="$1"
  local state
  state="$(az provider show --namespace "$namespace" --query registrationState -o tsv 2>/dev/null || true)"
  if [[ "$state" == "Registered" ]]; then
    return 0
  fi
  log "registering provider namespace: $namespace"
  az provider register --namespace "$namespace" --wait >/dev/null
}

ensure_postgres_db() {
  local db_name="$1"
  if az postgres flexible-server db show \
    --resource-group "$RESOURCE_GROUP" \
    --server-name "$POSTGRES_SERVER_NAME" \
    --database-name "$db_name" >/dev/null 2>&1; then
    log "postgres database already exists: $db_name"
    return 0
  fi

  log "creating postgres database: $db_name"
  az postgres flexible-server db create \
    --resource-group "$RESOURCE_GROUP" \
    --server-name "$POSTGRES_SERVER_NAME" \
    --database-name "$db_name" >/dev/null
}

ensure_postgres_firewall_rule() {
  local rule_name="$1"
  local start_ip="$2"
  local end_ip="$3"
  if az postgres flexible-server firewall-rule show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_SERVER_NAME" \
    --rule-name "$rule_name" >/dev/null 2>&1; then
    az postgres flexible-server firewall-rule update \
      --resource-group "$RESOURCE_GROUP" \
      --name "$POSTGRES_SERVER_NAME" \
      --rule-name "$rule_name" \
      --start-ip-address "$start_ip" \
      --end-ip-address "$end_ip" >/dev/null
    return 0
  fi

  az postgres flexible-server firewall-rule create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_SERVER_NAME" \
    --rule-name "$rule_name" \
    --start-ip-address "$start_ip" \
    --end-ip-address "$end_ip" >/dev/null
}

ensure_storage_subnet_rule() {
  local subnet_id="$1"
  local exists
  exists="$(az storage account network-rule list \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --query "virtualNetworkRules[?id=='${subnet_id}'] | length(@)" \
    -o tsv)"
  if [[ "$exists" != "0" ]]; then
    return 0
  fi
  az storage account network-rule add \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --subnet "$subnet_id" >/dev/null
}

ensure_storage_ip_rule() {
  local ip="$1"
  local exists
  exists="$(az storage account network-rule list \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --query "ipRules[?ipAddressOrRange=='${ip}'] | length(@)" \
    -o tsv)"
  if [[ "$exists" != "0" ]]; then
    return 0
  fi
  az storage account network-rule add \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --ip-address "$ip" >/dev/null
}

ensure_blob_role_assignment() {
  local principal_id="$1"
  local scope="$2"
  local existing
  existing="$(az role assignment list \
    --assignee-object-id "$principal_id" \
    --scope "$scope" \
    --role "Storage Blob Data Contributor" \
    --query "[0].id" -o tsv)"
  if [[ -n "$existing" ]]; then
    return 0
  fi

  retry 10 10 az role assignment create \
    --assignee-object-id "$principal_id" \
    --assignee-principal-type ServicePrincipal \
    --role "Storage Blob Data Contributor" \
    --scope "$scope" >/dev/null || die "failed to assign blob role at scope: $scope"
}

wait_for_principal_id() {
  local app_name="$1"
  local principal_id=""
  local i
  for ((i=1; i<=24; i++)); do
    principal_id="$(az containerapp show \
      --resource-group "$RESOURCE_GROUP" \
      --name "$app_name" \
      --query identity.principalId \
      -o tsv 2>/dev/null || true)"
    if [[ -n "$principal_id" && "$principal_id" != "None" ]]; then
      printf '%s' "$principal_id"
      return 0
    fi
    sleep 5
  done
  return 1
}

postgres_access_token() {
  local token
  token="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv 2>/dev/null || true)"
  if [[ -n "$token" ]]; then
    printf '%s' "$token"
    return 0
  fi
  az account get-access-token \
    --resource "https://ossrdbms-aad.database.windows.net" \
    --query accessToken \
    -o tsv
}

fetch_postgres_server_version() {
  local attempts=18
  local i
  local raw_version
  local version_token
  for ((i=1; i<=attempts; i++)); do
    PG_ACCESS_TOKEN="$(postgres_access_token)"
    raw_version="$(PGPASSWORD="$PG_ACCESS_TOKEN" psql \
      "host=${POSTGRES_FQDN} port=5432 dbname=postgres user=${ENTRA_ADMIN_UPN} sslmode=require" \
      -v ON_ERROR_STOP=1 \
      -Atq \
      -c "SHOW server_version;" 2>/dev/null || true)"
    version_token="$(printf '%s' "$raw_version" | awk '{print $1}')"
    if [[ -n "$version_token" ]]; then
      printf '%s' "$version_token"
      return 0
    fi
    sleep 10
  done
  return 1
}

verify_postgres_server_version() {
  local requested="$1"
  local actual="$2"
  if [[ "$requested" == *.* ]]; then
    [[ "$actual" == "$requested"* ]] || die "PostgreSQL version mismatch. Requested ${requested}, but server is ${actual}. Choose a region/SKU that supports ${requested}, or set POSTGRES_VERSION to a supported value."
    return 0
  fi
  [[ "$actual" == "$requested" || "$actual" == "${requested}."* ]] || die "PostgreSQL major version mismatch. Requested ${requested}, but server is ${actual}."
}

psql_exec() {
  local db_name="$1"
  local sql="$2"
  PGPASSWORD="$PG_ACCESS_TOKEN" psql \
    "host=${POSTGRES_FQDN} port=5432 dbname=${db_name} user=${ENTRA_ADMIN_UPN} sslmode=require" \
    -v ON_ERROR_STOP=1 \
    -q \
    -c "$sql" >/dev/null
}

ensure_pg_principal_mapping() {
  local role_name="$1"
  local object_id="$2"
  local role_lit
  local oid_lit
  role_lit="$(sql_escape_literal "$role_name")"
  oid_lit="$(sql_escape_literal "$object_id")"

  local primary_sql
  primary_sql=$(cat <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${role_lit}') THEN
    PERFORM pg_catalog.pgaadauth_create_principal_with_oid('${role_lit}', '${oid_lit}', 'service', false, false);
  END IF;
END
\$\$;
SQL
)

  if psql_exec "postgres" "$primary_sql"; then
    return 0
  fi

  log "fallback principal mapping path for role '${role_name}'"
  local fallback_sql
  fallback_sql=$(cat <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${role_lit}') THEN
    PERFORM pg_catalog.pgaadauth_create_principal('${role_lit}', false, false);
  END IF;
END
\$\$;
SQL
)
  psql_exec "postgres" "$fallback_sql"
}

grant_db_privileges() {
  local db_name="$1"
  local allowed_role="$2"
  local revoked_role="${3:-}"
  local db_ident
  local allow_ident
  local revoke_ident
  db_ident="$(sql_escape_ident "$db_name")"
  allow_ident="$(sql_escape_ident "$allowed_role")"
  revoke_ident="$(sql_escape_ident "$revoked_role")"

  local db_sql
  db_sql=$(cat <<SQL
GRANT CONNECT, CREATE, TEMP ON DATABASE "${db_ident}" TO "${allow_ident}";
SQL
)
  if [[ -n "$revoked_role" ]]; then
    db_sql+=$'\n'"REVOKE ALL PRIVILEGES ON DATABASE \"${db_ident}\" FROM \"${revoke_ident}\";"
  fi
  psql_exec "postgres" "$db_sql"

  local schema_sql
  schema_sql=$(cat <<SQL
GRANT USAGE, CREATE ON SCHEMA public TO "${allow_ident}";
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public TO "${allow_ident}";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "${allow_ident}";
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO "${allow_ident}";
SQL
)
  if [[ -n "$revoked_role" ]]; then
    schema_sql+=$'\n'"REVOKE ALL PRIVILEGES ON SCHEMA public FROM \"${revoke_ident}\";"
    schema_sql+=$'\n'"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM \"${revoke_ident}\";"
    schema_sql+=$'\n'"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM \"${revoke_ident}\";"
    schema_sql+=$'\n'"REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM \"${revoke_ident}\";"
  fi
  psql_exec "$db_name" "$schema_sql"
}

write_containerapp_yaml() {
  local file_path="$1"
  local app_name="$2"
  local image="$3"
  local web_url="$4"
  local database_url="$5"
  local secret_key="$6"
  local blob_container="$7"
  local min_replicas="$8"
  local max_replicas="$9"
  local storage_mount_name="${10}"

  cat >"$file_path" <<EOF
location: $(yaml_quote "$LOCATION")
name: $(yaml_quote "$app_name")
resourceGroup: $(yaml_quote "$RESOURCE_GROUP")
type: Microsoft.App/containerApps
identity:
  type: SystemAssigned
properties:
  managedEnvironmentId: $(yaml_quote "$ACA_ENV_ID")
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8000
      transport: Auto
      allowInsecure: false
    secrets:
      - name: ade-database-url
        value: $(yaml_quote "$database_url")
      - name: ade-secret-key
        value: $(yaml_quote "$secret_key")
  template:
    containers:
      - name: $(yaml_quote "$app_name")
        image: $(yaml_quote "$image")
        env:
          - name: ADE_SERVICES
            value: 'api,worker,web'
          - name: ADE_PUBLIC_WEB_URL
            value: $(yaml_quote "$web_url")
          - name: ADE_DATABASE_AUTH_MODE
            value: $(yaml_quote "$DATABASE_AUTH_MODE")
          - name: ADE_DATABASE_URL
            secretRef: ade-database-url
          - name: ADE_SECRET_KEY
            secretRef: ade-secret-key
          - name: ADE_BLOB_ACCOUNT_URL
            value: $(yaml_quote "https://${STORAGE_ACCOUNT_NAME}.blob.core.windows.net")
          - name: ADE_BLOB_CONTAINER
            value: $(yaml_quote "$blob_container")
          - name: ADE_DATA_DIR
            value: '/app/data'
          - name: ADE_AUTH_DISABLED
            value: 'false'
        volumeMounts:
          - volumeName: ade-data
            mountPath: /app/data
    scale:
      minReplicas: ${min_replicas}
      maxReplicas: ${max_replicas}
    volumes:
      - name: ade-data
        storageType: AzureFile
        storageName: $(yaml_quote "$storage_mount_name")
EOF
}

deploy_containerapp_from_yaml() {
  local app_name="$1"
  local yaml_path="$2"
  if az containerapp show --resource-group "$RESOURCE_GROUP" --name "$app_name" >/dev/null 2>&1; then
    log "updating container app: $app_name"
    az containerapp update \
      --resource-group "$RESOURCE_GROUP" \
      --name "$app_name" \
      --yaml "$yaml_path" >/dev/null
  else
    log "creating container app: $app_name"
    az containerapp create \
      --resource-group "$RESOURCE_GROUP" \
      --name "$app_name" \
      --yaml "$yaml_path" >/dev/null
  fi

  az containerapp identity assign \
    --resource-group "$RESOURCE_GROUP" \
    --name "$app_name" \
    --system-assigned >/dev/null
}

wait_for_http_200() {
  local url="$1"
  local attempts=30
  local i
  for ((i=1; i<=attempts; i++)); do
    if curl -fsS --max-time 15 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 10
  done
  return 1
}

SUBSCRIPTION_ID=""
LOCATION=""
NAME_STEM="automaticdataextractor"
NAME_SUFFIX=""
DEPLOY_DEV="true"

RESOURCE_GROUP=""
VNET_NAME=""
VNET_CIDR="10.80.0.0/16"
ACA_SUBNET_NAME=""
ACA_SUBNET_CIDR="10.80.0.0/23"
ACA_ENV_NAME=""
LOG_ANALYTICS_WORKSPACE_NAME=""

POSTGRES_SERVER_NAME=""
POSTGRES_ADMIN_USER=""
POSTGRES_ADMIN_PASSWORD=""
POSTGRES_PROD_DB="ade"
POSTGRES_DEV_DB="ade_dev"
POSTGRES_VERSION="18.1"
POSTGRES_VERSION_MAJOR=""
POSTGRES_VERSION_HAS_MINOR="false"
POSTGRES_TIER="Burstable"
POSTGRES_SKU_NAME="Standard_B1ms"
POSTGRES_STORAGE_SIZE_GB="32"

STORAGE_ACCOUNT_NAME=""
STORAGE_SKU="Standard_LRS"
BLOB_PROD_CONTAINER="ade-prod"
BLOB_DEV_CONTAINER="ade-dev"
FILE_PROD_SHARE="ade-data-prod"
FILE_DEV_SHARE="ade-data-dev"
PROD_STORAGE_MOUNT_NAME=""
DEV_STORAGE_MOUNT_NAME=""

PROD_APP_NAME=""
DEV_APP_NAME=""
PROD_IMAGE=""
DEV_IMAGE=""
PROD_WEB_URL=""
DEV_WEB_URL=""
PROD_SECRET_KEY=""
DEV_SECRET_KEY=""
PROD_DB_ROLE_NAME=""
DEV_DB_ROLE_NAME=""

DATABASE_AUTH_MODE="managed_identity"
ENABLE_FABRIC_AZURE_SERVICES_RULE="true"
VERIFY_DEPLOYMENT="true"
PROD_MIN_REPLICAS="1"
PROD_MAX_REPLICAS="2"
DEV_MIN_REPLICAS="0"
DEV_MAX_REPLICAS="1"

OPERATOR_IPS=()
OPERATOR_IPS_CSV="${OPERATOR_IPS_CSV:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      [[ $# -ge 2 ]] || die "--env-file requires a value"
      load_env_file "$2"
      shift 2
      ;;
    --name-stem) NAME_STEM="$2"; shift 2 ;;
    --name-suffix) NAME_SUFFIX="$2"; shift 2 ;;
    --deploy-dev) DEPLOY_DEV="$2"; shift 2 ;;
    --subscription-id) SUBSCRIPTION_ID="$2"; shift 2 ;;
    --resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
    --location) LOCATION="$2"; shift 2 ;;
    --vnet-name) VNET_NAME="$2"; shift 2 ;;
    --vnet-cidr) VNET_CIDR="$2"; shift 2 ;;
    --aca-subnet-name) ACA_SUBNET_NAME="$2"; shift 2 ;;
    --aca-subnet-cidr) ACA_SUBNET_CIDR="$2"; shift 2 ;;
    --aca-env-name) ACA_ENV_NAME="$2"; shift 2 ;;
    --log-analytics-workspace-name) LOG_ANALYTICS_WORKSPACE_NAME="$2"; shift 2 ;;
    --postgres-server-name) POSTGRES_SERVER_NAME="$2"; shift 2 ;;
    --postgres-admin-user) POSTGRES_ADMIN_USER="$2"; shift 2 ;;
    --postgres-admin-password) POSTGRES_ADMIN_PASSWORD="$2"; shift 2 ;;
    --postgres-prod-db) POSTGRES_PROD_DB="$2"; shift 2 ;;
    --postgres-dev-db) POSTGRES_DEV_DB="$2"; shift 2 ;;
    --postgres-version) POSTGRES_VERSION="$2"; shift 2 ;;
    --postgres-tier) POSTGRES_TIER="$2"; shift 2 ;;
    --postgres-sku-name) POSTGRES_SKU_NAME="$2"; shift 2 ;;
    --postgres-storage-size-gb) POSTGRES_STORAGE_SIZE_GB="$2"; shift 2 ;;
    --storage-account-name) STORAGE_ACCOUNT_NAME="$2"; shift 2 ;;
    --storage-sku) STORAGE_SKU="$2"; shift 2 ;;
    --blob-prod-container) BLOB_PROD_CONTAINER="$2"; shift 2 ;;
    --blob-dev-container) BLOB_DEV_CONTAINER="$2"; shift 2 ;;
    --file-prod-share) FILE_PROD_SHARE="$2"; shift 2 ;;
    --file-dev-share) FILE_DEV_SHARE="$2"; shift 2 ;;
    --prod-storage-mount-name) PROD_STORAGE_MOUNT_NAME="$2"; shift 2 ;;
    --dev-storage-mount-name) DEV_STORAGE_MOUNT_NAME="$2"; shift 2 ;;
    --prod-app-name) PROD_APP_NAME="$2"; shift 2 ;;
    --dev-app-name) DEV_APP_NAME="$2"; shift 2 ;;
    --prod-image) PROD_IMAGE="$2"; shift 2 ;;
    --dev-image) DEV_IMAGE="$2"; shift 2 ;;
    --prod-web-url) PROD_WEB_URL="$2"; shift 2 ;;
    --dev-web-url) DEV_WEB_URL="$2"; shift 2 ;;
    --prod-secret-key) PROD_SECRET_KEY="$2"; shift 2 ;;
    --dev-secret-key) DEV_SECRET_KEY="$2"; shift 2 ;;
    --prod-db-role-name) PROD_DB_ROLE_NAME="$2"; shift 2 ;;
    --dev-db-role-name) DEV_DB_ROLE_NAME="$2"; shift 2 ;;
    --database-auth-mode) DATABASE_AUTH_MODE="$2"; shift 2 ;;
    --enable-fabric-azure-services-rule) ENABLE_FABRIC_AZURE_SERVICES_RULE="$2"; shift 2 ;;
    --verify-deployment) VERIFY_DEPLOYMENT="$2"; shift 2 ;;
    --prod-min-replicas) PROD_MIN_REPLICAS="$2"; shift 2 ;;
    --prod-max-replicas) PROD_MAX_REPLICAS="$2"; shift 2 ;;
    --dev-min-replicas) DEV_MIN_REPLICAS="$2"; shift 2 ;;
    --dev-max-replicas) DEV_MAX_REPLICAS="$2"; shift 2 ;;
    --operator-ip)
      [[ $# -ge 2 ]] || die "--operator-ip requires a value"
      OPERATOR_IPS+=("$2")
      shift 2
      ;;
    --operator-ips-csv)
      [[ $# -ge 2 ]] || die "--operator-ips-csv requires a value"
      OPERATOR_IPS_CSV="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

ENABLE_FABRIC_AZURE_SERVICES_RULE="$(normalize_bool "$ENABLE_FABRIC_AZURE_SERVICES_RULE")"
VERIFY_DEPLOYMENT="$(normalize_bool "$VERIFY_DEPLOYMENT")"
DEPLOY_DEV="$(normalize_bool "$DEPLOY_DEV")"

if [[ -n "${OPERATOR_IPS_CSV:-}" ]]; then
  IFS=',' read -r -a _parsed_ips <<<"$OPERATOR_IPS_CSV"
  for raw_ip in "${_parsed_ips[@]}"; do
    ip="$(trim "$raw_ip")"
    [[ -n "$ip" ]] && OPERATOR_IPS+=("$ip")
  done
fi

require_non_empty "$SUBSCRIPTION_ID" "subscription-id"
require_non_empty "$LOCATION" "location"
require_non_empty "$POSTGRES_ADMIN_USER" "postgres-admin-user"
require_non_empty "$POSTGRES_ADMIN_PASSWORD" "postgres-admin-password"
require_non_empty "$PROD_IMAGE" "prod-image"
require_non_empty "$PROD_WEB_URL" "prod-web-url"
require_non_empty "$PROD_SECRET_KEY" "prod-secret-key"
parse_postgres_version "$POSTGRES_VERSION"

STEM_DASH="$(sanitize_dash_token "$NAME_STEM")"
STEM_ALNUM="$(sanitize_alnum_token "$NAME_STEM")"
SUFFIX_DASH="$(sanitize_dash_token "$NAME_SUFFIX")"
SUFFIX_ALNUM="$(sanitize_alnum_token "$NAME_SUFFIX")"
LOCATION_TOKEN="$(sanitize_dash_token "$LOCATION")"

require_non_empty "$STEM_DASH" "name stem (alphanumeric token)"
require_non_empty "$STEM_ALNUM" "name stem (storage-safe alphanumeric token)"
require_non_empty "$LOCATION_TOKEN" "location token"

if [[ -z "$RESOURCE_GROUP" ]]; then
  RESOURCE_GROUP="$(append_suffix_dash "rg-${STEM_DASH}" "$SUFFIX_DASH")"
fi
if [[ -z "$VNET_NAME" ]]; then
  VNET_NAME="$(append_suffix_dash "vnet-${STEM_DASH}" "$SUFFIX_DASH")"
fi
if [[ -z "$ACA_SUBNET_NAME" ]]; then
  ACA_SUBNET_NAME="$(append_suffix_dash "snet-${STEM_DASH}-aca" "$SUFFIX_DASH")"
fi
if [[ -z "$ACA_ENV_NAME" ]]; then
  ACA_ENV_NAME="$(append_suffix_dash "cae-${STEM_DASH}-${LOCATION_TOKEN}" "$SUFFIX_DASH")"
fi
if [[ -z "$LOG_ANALYTICS_WORKSPACE_NAME" ]]; then
  LOG_ANALYTICS_WORKSPACE_NAME="$(append_suffix_dash "log-${STEM_DASH}" "$SUFFIX_DASH")"
fi
if [[ -z "$POSTGRES_SERVER_NAME" ]]; then
  POSTGRES_SERVER_NAME="$(append_suffix_dash "psql-${STEM_DASH}-${LOCATION_TOKEN}" "$SUFFIX_DASH")"
fi
if [[ -z "$STORAGE_ACCOUNT_NAME" ]]; then
  STORAGE_ACCOUNT_NAME="$(append_suffix_alnum "sa${STEM_ALNUM}" "$SUFFIX_ALNUM")"
fi
if [[ -z "$PROD_APP_NAME" ]]; then
  PROD_APP_NAME="$(append_suffix_dash "ca-${STEM_DASH}-prod" "$SUFFIX_DASH")"
fi
if [[ -z "$DEV_APP_NAME" && "$DEPLOY_DEV" == "true" ]]; then
  DEV_APP_NAME="$(append_suffix_dash "ca-${STEM_DASH}-dev" "$SUFFIX_DASH")"
fi
if [[ -z "$PROD_STORAGE_MOUNT_NAME" ]]; then
  PROD_STORAGE_MOUNT_NAME="$(append_suffix_dash "share-${STEM_DASH}-prod" "$SUFFIX_DASH")"
fi
if [[ -z "$DEV_STORAGE_MOUNT_NAME" && "$DEPLOY_DEV" == "true" ]]; then
  DEV_STORAGE_MOUNT_NAME="$(append_suffix_dash "share-${STEM_DASH}-dev" "$SUFFIX_DASH")"
fi
if [[ -z "$DEV_IMAGE" && "$DEPLOY_DEV" == "true" ]]; then
  DEV_IMAGE="$PROD_IMAGE"
fi
if [[ -z "$PROD_DB_ROLE_NAME" ]]; then
  PROD_DB_ROLE_NAME="$PROD_APP_NAME"
fi
if [[ -z "$DEV_DB_ROLE_NAME" && "$DEPLOY_DEV" == "true" ]]; then
  DEV_DB_ROLE_NAME="$DEV_APP_NAME"
fi

[[ "$DATABASE_AUTH_MODE" == "managed_identity" ]] || die "only --database-auth-mode managed_identity is supported"
[[ "$POSTGRES_SERVER_NAME" =~ ^[a-z][a-z0-9-]{1,61}[a-z0-9]$ ]] || die "postgres server name must be 3-63 chars, lowercase alnum/hyphen, start with letter, end with alnum. Override with POSTGRES_SERVER_NAME or --postgres-server-name."
[[ "$STORAGE_ACCOUNT_NAME" =~ ^[a-z0-9]{3,24}$ ]] || die "storage account name must be 3-24 lowercase letters/numbers. Override with STORAGE_ACCOUNT_NAME or --storage-account-name."
[[ "$LOG_ANALYTICS_WORKSPACE_NAME" =~ ^[a-z0-9][a-z0-9-]{2,61}[a-z0-9]$ ]] || die "log analytics workspace name must be 4-63 chars, lowercase alnum/hyphen, start/end with alnum. Override with LOG_ANALYTICS_WORKSPACE_NAME or --log-analytics-workspace-name."

if [[ "$DEPLOY_DEV" == "true" ]]; then
  require_non_empty "$DEV_WEB_URL" "dev-web-url (required when --deploy-dev=true)"
  require_non_empty "$DEV_SECRET_KEY" "dev-secret-key (required when --deploy-dev=true)"
  require_non_empty "$DEV_APP_NAME" "dev-app-name (required when --deploy-dev=true)"
  require_non_empty "$DEV_IMAGE" "dev-image (required when --deploy-dev=true)"
  require_non_empty "$DEV_DB_ROLE_NAME" "dev-db-role-name (required when --deploy-dev=true)"
  [[ "$PROD_APP_NAME" != "$DEV_APP_NAME" ]] || die "prod and dev app names must differ"
  [[ "$POSTGRES_PROD_DB" != "$POSTGRES_DEV_DB" ]] || die "prod and dev database names must differ"
  [[ "$PROD_DB_ROLE_NAME" != "$DEV_DB_ROLE_NAME" ]] || die "prod and dev DB role names must differ"
fi

is_cidr "$VNET_CIDR" || die "invalid CIDR for --vnet-cidr: $VNET_CIDR"
is_cidr "$ACA_SUBNET_CIDR" || die "invalid CIDR for --aca-subnet-cidr: $ACA_SUBNET_CIDR"
validate_cidr_relationship "$VNET_CIDR" "$ACA_SUBNET_CIDR" || die "ACA subnet CIDR must be contained inside the VNet CIDR"

if [[ ${#OPERATOR_IPS[@]} -gt 0 ]]; then
  for ip in "${OPERATOR_IPS[@]}"; do
    is_ipv4 "$ip" || die "invalid operator IPv4 address: $ip"
  done
fi

require_cmd az
require_cmd curl
require_cmd psql

if az extension show --name containerapp >/dev/null 2>&1; then
  log "updating Azure CLI containerapp extension"
  az extension update --name containerapp >/dev/null
else
  log "installing Azure CLI containerapp extension"
  az extension add --name containerapp >/dev/null
fi

log "setting Azure subscription context"
az account set --subscription "$SUBSCRIPTION_ID"

ENTRA_ADMIN_OBJECT_ID="$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)"
ENTRA_ADMIN_UPN="$(az ad signed-in-user show --query userPrincipalName -o tsv 2>/dev/null || true)"
ENTRA_ADMIN_DISPLAY_NAME="$(az ad signed-in-user show --query displayName -o tsv 2>/dev/null || true)"

require_non_empty "$ENTRA_ADMIN_OBJECT_ID" "signed-in Entra user object id (az ad signed-in-user show)"
require_non_empty "$ENTRA_ADMIN_UPN" "signed-in Entra user UPN (az ad signed-in-user show)"
require_non_empty "$ENTRA_ADMIN_DISPLAY_NAME" "signed-in Entra display name (az ad signed-in-user show)"

for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.DBforPostgreSQL Microsoft.Storage Microsoft.Network; do
  ensure_provider_registered "$ns"
done

log "ensuring resource group"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" >/dev/null

if az monitor log-analytics workspace show --resource-group "$RESOURCE_GROUP" --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" >/dev/null 2>&1; then
  log "log analytics workspace already exists: $LOG_ANALYTICS_WORKSPACE_NAME"
else
  log "creating log analytics workspace: $LOG_ANALYTICS_WORKSPACE_NAME"
  az monitor log-analytics workspace create \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" \
    --location "$LOCATION" >/dev/null
fi

LOG_ANALYTICS_WORKSPACE_CUSTOMER_ID="$(az monitor log-analytics workspace show \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" \
  --query customerId -o tsv)"
require_non_empty "$LOG_ANALYTICS_WORKSPACE_CUSTOMER_ID" "log analytics workspace customer id"

if az network vnet show --resource-group "$RESOURCE_GROUP" --name "$VNET_NAME" >/dev/null 2>&1; then
  log "vnet already exists: $VNET_NAME"
else
  log "creating vnet: $VNET_NAME"
  az network vnet create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$VNET_NAME" \
    --location "$LOCATION" \
    --address-prefixes "$VNET_CIDR" \
    --subnet-name "$ACA_SUBNET_NAME" \
    --subnet-prefixes "$ACA_SUBNET_CIDR" >/dev/null
fi

if az network vnet subnet show --resource-group "$RESOURCE_GROUP" --vnet-name "$VNET_NAME" --name "$ACA_SUBNET_NAME" >/dev/null 2>&1; then
  log "subnet already exists: $ACA_SUBNET_NAME"
else
  log "creating subnet: $ACA_SUBNET_NAME"
  az network vnet subnet create \
    --resource-group "$RESOURCE_GROUP" \
    --vnet-name "$VNET_NAME" \
    --name "$ACA_SUBNET_NAME" \
    --address-prefixes "$ACA_SUBNET_CIDR" >/dev/null
fi

SUBNET_DELEGATIONS="$(az network vnet subnet show \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --name "$ACA_SUBNET_NAME" \
  --query "delegations[].serviceName" \
  -o tsv)"
if ! printf '%s\n' "$SUBNET_DELEGATIONS" | grep -qx "Microsoft.App/environments"; then
  log "delegating subnet to Microsoft.App/environments"
  az network vnet subnet update \
    --resource-group "$RESOURCE_GROUP" \
    --vnet-name "$VNET_NAME" \
    --name "$ACA_SUBNET_NAME" \
    --delegations Microsoft.App/environments >/dev/null
fi

SUBNET_ENDPOINTS="$(az network vnet subnet show \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --name "$ACA_SUBNET_NAME" \
  --query "serviceEndpoints[].service" \
  -o tsv)"
if ! printf '%s\n' "$SUBNET_ENDPOINTS" | grep -qx "Microsoft.Storage"; then
  log "enabling Microsoft.Storage service endpoint on ACA subnet"
  az network vnet subnet update \
    --resource-group "$RESOURCE_GROUP" \
    --vnet-name "$VNET_NAME" \
    --name "$ACA_SUBNET_NAME" \
    --service-endpoints Microsoft.Storage >/dev/null
fi

ACA_SUBNET_ID="$(az network vnet subnet show --resource-group "$RESOURCE_GROUP" --vnet-name "$VNET_NAME" --name "$ACA_SUBNET_NAME" --query id -o tsv)"

if az containerapp env show --resource-group "$RESOURCE_GROUP" --name "$ACA_ENV_NAME" >/dev/null 2>&1; then
  log "container apps environment already exists: $ACA_ENV_NAME"
  ACA_CURRENT_LOG_DESTINATION="$(az containerapp env show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACA_ENV_NAME" \
    --query properties.appLogsConfiguration.destination \
    -o tsv 2>/dev/null || true)"
  ACA_CURRENT_LOG_WORKSPACE_CUSTOMER_ID="$(az containerapp env show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACA_ENV_NAME" \
    --query properties.appLogsConfiguration.logAnalyticsConfiguration.customerId \
    -o tsv 2>/dev/null || true)"
  if [[ "$ACA_CURRENT_LOG_DESTINATION" == "log-analytics" && "$ACA_CURRENT_LOG_WORKSPACE_CUSTOMER_ID" == "$LOG_ANALYTICS_WORKSPACE_CUSTOMER_ID" ]]; then
    log "container apps environment logging already targets: $LOG_ANALYTICS_WORKSPACE_NAME"
  else
    LOG_ANALYTICS_WORKSPACE_SHARED_KEY="$(az monitor log-analytics workspace get-shared-keys \
      --resource-group "$RESOURCE_GROUP" \
      --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" \
      --query primarySharedKey -o tsv)"
    require_non_empty "$LOG_ANALYTICS_WORKSPACE_SHARED_KEY" "log analytics workspace shared key"
    log "updating container apps environment logging workspace: $LOG_ANALYTICS_WORKSPACE_NAME"
    az containerapp env update \
      --resource-group "$RESOURCE_GROUP" \
      --name "$ACA_ENV_NAME" \
      --logs-destination log-analytics \
      --logs-workspace-id "$LOG_ANALYTICS_WORKSPACE_CUSTOMER_ID" \
      --logs-workspace-key "$LOG_ANALYTICS_WORKSPACE_SHARED_KEY" >/dev/null
  fi
else
  LOG_ANALYTICS_WORKSPACE_SHARED_KEY="$(az monitor log-analytics workspace get-shared-keys \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" \
    --query primarySharedKey -o tsv)"
  require_non_empty "$LOG_ANALYTICS_WORKSPACE_SHARED_KEY" "log analytics workspace shared key"
  log "creating container apps environment: $ACA_ENV_NAME"
  az containerapp env create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACA_ENV_NAME" \
    --location "$LOCATION" \
    --logs-destination log-analytics \
    --logs-workspace-id "$LOG_ANALYTICS_WORKSPACE_CUSTOMER_ID" \
    --logs-workspace-key "$LOG_ANALYTICS_WORKSPACE_SHARED_KEY" \
    --infrastructure-subnet-resource-id "$ACA_SUBNET_ID" >/dev/null
fi

ACA_ENV_ID="$(az containerapp env show --resource-group "$RESOURCE_GROUP" --name "$ACA_ENV_NAME" --query id -o tsv)"

if az postgres flexible-server show --resource-group "$RESOURCE_GROUP" --name "$POSTGRES_SERVER_NAME" >/dev/null 2>&1; then
  log "postgres server already exists: $POSTGRES_SERVER_NAME"
else
  log "creating postgres flexible server: $POSTGRES_SERVER_NAME (requested version ${POSTGRES_VERSION}, create major ${POSTGRES_VERSION_MAJOR})"
  az postgres flexible-server create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_SERVER_NAME" \
    --location "$LOCATION" \
    --admin-user "$POSTGRES_ADMIN_USER" \
    --admin-password "$POSTGRES_ADMIN_PASSWORD" \
    --version "$POSTGRES_VERSION_MAJOR" \
    --tier "$POSTGRES_TIER" \
    --sku-name "$POSTGRES_SKU_NAME" \
    --storage-size "$POSTGRES_STORAGE_SIZE_GB" \
    --public-access Enabled >/dev/null
fi

log "ensuring postgres authentication/network mode"
az postgres flexible-server update \
  --resource-group "$RESOURCE_GROUP" \
  --name "$POSTGRES_SERVER_NAME" \
  --public-access Enabled \
  --microsoft-entra-auth Enabled \
  --password-auth Enabled >/dev/null

POSTGRES_FQDN="$(az postgres flexible-server show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$POSTGRES_SERVER_NAME" \
  --query fullyQualifiedDomainName -o tsv)"

ensure_postgres_db "$POSTGRES_PROD_DB"
if [[ "$DEPLOY_DEV" == "true" ]]; then
  ensure_postgres_db "$POSTGRES_DEV_DB"
fi

if [[ "$ENABLE_FABRIC_AZURE_SERVICES_RULE" == "true" ]]; then
  log "ensuring Fabric-compatible Azure-services firewall rule on PostgreSQL"
  ensure_postgres_firewall_rule "allow-azure-services" "0.0.0.0" "0.0.0.0"
fi

if [[ ${#OPERATOR_IPS[@]} -gt 0 ]]; then
  for ip in "${OPERATOR_IPS[@]}"; do
    safe_ip="${ip//./-}"
    ensure_postgres_firewall_rule "operator-${safe_ip}" "$ip" "$ip"
  done
fi

if az postgres flexible-server microsoft-entra-admin show \
  --resource-group "$RESOURCE_GROUP" \
  --server-name "$POSTGRES_SERVER_NAME" \
  --object-id "$ENTRA_ADMIN_OBJECT_ID" >/dev/null 2>&1; then
  log "signed-in user is already an Entra admin on PostgreSQL"
else
  log "assigning signed-in user as PostgreSQL Entra admin"
  az postgres flexible-server microsoft-entra-admin create \
    --resource-group "$RESOURCE_GROUP" \
    --server-name "$POSTGRES_SERVER_NAME" \
    --display-name "$ENTRA_ADMIN_DISPLAY_NAME" \
    --object-id "$ENTRA_ADMIN_OBJECT_ID" \
    --type User >/dev/null
fi

log "verifying PostgreSQL runtime server version against requested ${POSTGRES_VERSION}"
ACTUAL_POSTGRES_VERSION="$(fetch_postgres_server_version)" || die "unable to query PostgreSQL server_version via Entra auth"
verify_postgres_server_version "$POSTGRES_VERSION" "$ACTUAL_POSTGRES_VERSION"

if az storage account show --resource-group "$RESOURCE_GROUP" --name "$STORAGE_ACCOUNT_NAME" >/dev/null 2>&1; then
  log "storage account already exists: $STORAGE_ACCOUNT_NAME"
else
  name_available="$(az storage account check-name --name "$STORAGE_ACCOUNT_NAME" --query nameAvailable -o tsv)"
  if [[ "$name_available" != "true" ]]; then
    die "storage account name '${STORAGE_ACCOUNT_NAME}' is not available. Set STORAGE_ACCOUNT_NAME or pass --storage-account-name."
  fi
  log "creating storage account: $STORAGE_ACCOUNT_NAME"
  az storage account create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$STORAGE_ACCOUNT_NAME" \
    --location "$LOCATION" \
    --kind StorageV2 \
    --sku "$STORAGE_SKU" \
    --allow-blob-public-access false >/dev/null
fi

log "ensuring storage firewall policy"
az storage account update \
  --resource-group "$RESOURCE_GROUP" \
  --name "$STORAGE_ACCOUNT_NAME" \
  --public-network-access Enabled \
  --default-action Deny >/dev/null

ensure_storage_subnet_rule "$ACA_SUBNET_ID"
if [[ ${#OPERATOR_IPS[@]} -gt 0 ]]; then
  for ip in "${OPERATOR_IPS[@]}"; do
    ensure_storage_ip_rule "$ip"
  done
fi

STORAGE_ACCOUNT_KEY="$(az storage account keys list \
  --resource-group "$RESOURCE_GROUP" \
  --account-name "$STORAGE_ACCOUNT_NAME" \
  --query "[0].value" -o tsv)"

log "ensuring blob containers"
az storage container create \
  --name "$BLOB_PROD_CONTAINER" \
  --account-name "$STORAGE_ACCOUNT_NAME" \
  --account-key "$STORAGE_ACCOUNT_KEY" >/dev/null
if [[ "$DEPLOY_DEV" == "true" ]]; then
  az storage container create \
    --name "$BLOB_DEV_CONTAINER" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_ACCOUNT_KEY" >/dev/null
fi

log "ensuring Azure Files shares"
az storage share create \
  --name "$FILE_PROD_SHARE" \
  --account-name "$STORAGE_ACCOUNT_NAME" \
  --account-key "$STORAGE_ACCOUNT_KEY" \
  --quota 1024 >/dev/null
if [[ "$DEPLOY_DEV" == "true" ]]; then
  az storage share create \
    --name "$FILE_DEV_SHARE" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_ACCOUNT_KEY" \
    --quota 1024 >/dev/null
fi

log "registering Azure Files mounts in ACA environment"
az containerapp env storage set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACA_ENV_NAME" \
  --storage-name "$PROD_STORAGE_MOUNT_NAME" \
  --access-mode ReadWrite \
  --azure-file-account-name "$STORAGE_ACCOUNT_NAME" \
  --azure-file-account-key "$STORAGE_ACCOUNT_KEY" \
  --azure-file-share-name "$FILE_PROD_SHARE" >/dev/null
if [[ "$DEPLOY_DEV" == "true" ]]; then
  az containerapp env storage set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACA_ENV_NAME" \
    --storage-name "$DEV_STORAGE_MOUNT_NAME" \
    --access-mode ReadWrite \
    --azure-file-account-name "$STORAGE_ACCOUNT_NAME" \
    --azure-file-account-key "$STORAGE_ACCOUNT_KEY" \
    --azure-file-share-name "$FILE_DEV_SHARE" >/dev/null
fi

PROD_DATABASE_URL="postgresql+psycopg://${PROD_DB_ROLE_NAME}@${POSTGRES_FQDN}:5432/${POSTGRES_PROD_DB}?sslmode=require"
if [[ "$DEPLOY_DEV" == "true" ]]; then
  DEV_DATABASE_URL="postgresql+psycopg://${DEV_DB_ROLE_NAME}@${POSTGRES_FQDN}:5432/${POSTGRES_DEV_DB}?sslmode=require"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PROD_YAML="$TMP_DIR/prod-containerapp.yaml"
write_containerapp_yaml \
  "$PROD_YAML" \
  "$PROD_APP_NAME" \
  "$PROD_IMAGE" \
  "$PROD_WEB_URL" \
  "$PROD_DATABASE_URL" \
  "$PROD_SECRET_KEY" \
  "$BLOB_PROD_CONTAINER" \
  "$PROD_MIN_REPLICAS" \
  "$PROD_MAX_REPLICAS" \
  "$PROD_STORAGE_MOUNT_NAME"

deploy_containerapp_from_yaml "$PROD_APP_NAME" "$PROD_YAML"
if [[ "$DEPLOY_DEV" == "true" ]]; then
  DEV_YAML="$TMP_DIR/dev-containerapp.yaml"
  write_containerapp_yaml \
    "$DEV_YAML" \
    "$DEV_APP_NAME" \
    "$DEV_IMAGE" \
    "$DEV_WEB_URL" \
    "$DEV_DATABASE_URL" \
    "$DEV_SECRET_KEY" \
    "$BLOB_DEV_CONTAINER" \
    "$DEV_MIN_REPLICAS" \
    "$DEV_MAX_REPLICAS" \
    "$DEV_STORAGE_MOUNT_NAME"
  deploy_containerapp_from_yaml "$DEV_APP_NAME" "$DEV_YAML"
fi

log "waiting for container app principal IDs"
PROD_APP_PRINCIPAL_ID="$(wait_for_principal_id "$PROD_APP_NAME")" || die "unable to resolve principal ID for $PROD_APP_NAME"
if [[ "$DEPLOY_DEV" == "true" ]]; then
  DEV_APP_PRINCIPAL_ID="$(wait_for_principal_id "$DEV_APP_NAME")" || die "unable to resolve principal ID for $DEV_APP_NAME"
fi

PROD_BLOB_SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${BLOB_PROD_CONTAINER}"
if [[ "$DEPLOY_DEV" == "true" ]]; then
  DEV_BLOB_SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${BLOB_DEV_CONTAINER}"
fi

log "ensuring blob RBAC assignments"
ensure_blob_role_assignment "$PROD_APP_PRINCIPAL_ID" "$PROD_BLOB_SCOPE"
if [[ "$DEPLOY_DEV" == "true" ]]; then
  ensure_blob_role_assignment "$DEV_APP_PRINCIPAL_ID" "$DEV_BLOB_SCOPE"
fi

log "provisioning PostgreSQL Entra principals and DB grants"
PG_ACCESS_TOKEN="$(postgres_access_token)"
ensure_pg_principal_mapping "$PROD_DB_ROLE_NAME" "$PROD_APP_PRINCIPAL_ID"
if [[ "$DEPLOY_DEV" == "true" ]]; then
  ensure_pg_principal_mapping "$DEV_DB_ROLE_NAME" "$DEV_APP_PRINCIPAL_ID"
  grant_db_privileges "$POSTGRES_PROD_DB" "$PROD_DB_ROLE_NAME" "$DEV_DB_ROLE_NAME"
  grant_db_privileges "$POSTGRES_DEV_DB" "$DEV_DB_ROLE_NAME" "$PROD_DB_ROLE_NAME"
else
  grant_db_privileges "$POSTGRES_PROD_DB" "$PROD_DB_ROLE_NAME"
fi

PROD_FQDN="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$PROD_APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)"
DEV_FQDN=""
if [[ "$DEPLOY_DEV" == "true" ]]; then
  DEV_FQDN="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$DEV_APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)"
fi

if [[ "$VERIFY_DEPLOYMENT" == "true" ]]; then
  log "running deployment verification checks"

  if [[ -n "$PROD_FQDN" ]]; then
    wait_for_http_200 "https://${PROD_FQDN}/api/v1/health" || die "prod health check failed: https://${PROD_FQDN}/api/v1/health"
    wait_for_http_200 "https://${PROD_FQDN}/api/v1/info" || die "prod info check failed: https://${PROD_FQDN}/api/v1/info"
  fi
  if [[ "$DEPLOY_DEV" == "true" && -n "$DEV_FQDN" ]]; then
    wait_for_http_200 "https://${DEV_FQDN}/api/v1/health" || log "warning: dev health check did not pass in verify window (dev may be scaled to zero)"
    wait_for_http_200 "https://${DEV_FQDN}/api/v1/info" || log "warning: dev info check did not pass in verify window (dev may be scaled to zero)"
  fi

  prod_min="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$PROD_APP_NAME" --query properties.template.scale.minReplicas -o tsv)"
  [[ "$prod_min" == "$PROD_MIN_REPLICAS" ]] || die "prod min replicas mismatch: expected $PROD_MIN_REPLICAS got $prod_min"
  if [[ "$DEPLOY_DEV" == "true" ]]; then
    dev_min="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$DEV_APP_NAME" --query properties.template.scale.minReplicas -o tsv)"
    [[ "$dev_min" == "$DEV_MIN_REPLICAS" ]] || die "dev min replicas mismatch: expected $DEV_MIN_REPLICAS got $dev_min"
  fi

  prod_auth_mode="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$PROD_APP_NAME" --query "properties.template.containers[0].env[?name=='ADE_DATABASE_AUTH_MODE'].value | [0]" -o tsv)"
  [[ "$prod_auth_mode" == "managed_identity" ]] || die "prod ADE_DATABASE_AUTH_MODE is not managed_identity"
  if [[ "$DEPLOY_DEV" == "true" ]]; then
    dev_auth_mode="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$DEV_APP_NAME" --query "properties.template.containers[0].env[?name=='ADE_DATABASE_AUTH_MODE'].value | [0]" -o tsv)"
    [[ "$dev_auth_mode" == "managed_identity" ]] || die "dev ADE_DATABASE_AUTH_MODE is not managed_identity"
  fi

  storage_default_action="$(az storage account show --resource-group "$RESOURCE_GROUP" --name "$STORAGE_ACCOUNT_NAME" --query networkRuleSet.defaultAction -o tsv)"
  [[ "$storage_default_action" == "Deny" ]] || die "storage firewall default action is not Deny"

  if [[ "$ENABLE_FABRIC_AZURE_SERVICES_RULE" == "true" ]]; then
    az postgres flexible-server firewall-rule show \
      --resource-group "$RESOURCE_GROUP" \
      --name "$POSTGRES_SERVER_NAME" \
      --rule-name allow-azure-services >/dev/null || die "missing PostgreSQL allow-azure-services firewall rule"
  fi
fi

cat <<EOF

Bootstrap complete.

Resource group:          ${RESOURCE_GROUP}
Location:                ${LOCATION}
VNet / Subnet:           ${VNET_NAME} / ${ACA_SUBNET_NAME}
ACA environment:         ${ACA_ENV_NAME}
Log Analytics workspace: ${LOG_ANALYTICS_WORKSPACE_NAME}
PostgreSQL server:       ${POSTGRES_SERVER_NAME}
PostgreSQL version:      requested ${POSTGRES_VERSION} / actual ${ACTUAL_POSTGRES_VERSION}
PostgreSQL FQDN:         ${POSTGRES_FQDN}
PostgreSQL databases:    ${POSTGRES_PROD_DB}$( [[ "$DEPLOY_DEV" == "true" ]] && printf ', %s' "$POSTGRES_DEV_DB")
Storage account:         ${STORAGE_ACCOUNT_NAME}
Blob containers:         ${BLOB_PROD_CONTAINER}$( [[ "$DEPLOY_DEV" == "true" ]] && printf ', %s' "$BLOB_DEV_CONTAINER")
Azure Files shares:      ${FILE_PROD_SHARE}$( [[ "$DEPLOY_DEV" == "true" ]] && printf ', %s' "$FILE_DEV_SHARE")
Prod app:                ${PROD_APP_NAME} (https://${PROD_FQDN})
Prod DB URL user:        ${PROD_DB_ROLE_NAME}
$( [[ "$DEPLOY_DEV" == "true" ]] && printf 'Dev app:                 %s (https://%s)\n' "$DEV_APP_NAME" "$DEV_FQDN")
$( [[ "$DEPLOY_DEV" == "true" ]] && printf 'Dev DB URL user:         %s\n' "$DEV_DB_ROLE_NAME")

Manual validation still required:
  1. Upload/run/download flow in prod UI.
$( [[ "$DEPLOY_DEV" == "true" ]] && printf '  2. Upload/run/download flow in dev UI.\n  3. Confirm dev scales to zero when idle in Azure Portal.\n  4. Confirm Fabric mirroring connectivity against PostgreSQL public endpoint.' || printf '  2. Confirm Fabric mirroring connectivity against PostgreSQL public endpoint.' )
EOF
