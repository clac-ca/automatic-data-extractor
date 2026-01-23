#!/usr/bin/env bash
set -euo pipefail

#
# scripts/db/wait-for-sql.sh
#
# Waits until SQL Server is accepting logins.
#
# Requires: sqlcmd (installed in devcontainer via mssql-tools18)
#
# Env (defaults match .env.example):
#   ADE_SQL_HOST (default: sql)
#   ADE_SQL_PORT (default: 1433)
#   ADE_SQL_USER (default: sa)
#   ADE_SQL_PASSWORD
#   ADE_SQL_ENCRYPT (default: yes)  # ODBC Driver 18 encrypt default is 'yes'
#
# Note on ODBC18 encryption:
# - sqlcmd is secure by default. Use `-No` for optional encryption when talking to local containers.
#

HOST="${ADE_SQL_HOST:-sql}"
PORT="${ADE_SQL_PORT:-1433}"
USER="${ADE_SQL_USER:-sa}"
PASSWORD="${ADE_SQL_PASSWORD:-}"
ENCRYPT="${ADE_SQL_ENCRYPT:-optional}"

if [[ -z "${PASSWORD}" ]]; then
  echo "ERROR: ADE_SQL_PASSWORD is not set." >&2
  exit 1
fi

if ! command -v sqlcmd >/dev/null 2>&1; then
  echo "ERROR: sqlcmd not found. Install mssql-tools18 or run inside the devcontainer." >&2
  exit 1
fi

# For local dev containers, optional encryption usually avoids TLS validation issues.
SQLCMD_ENCRYPT_FLAG=""
if [[ "${ENCRYPT}" == "optional" ]]; then
  SQLCMD_ENCRYPT_FLAG="-No"
elif [[ "${ENCRYPT}" == "yes" || "${ENCRYPT}" == "true" ]]; then
  SQLCMD_ENCRYPT_FLAG="-N"
elif [[ "${ENCRYPT}" == "no" || "${ENCRYPT}" == "false" ]]; then
  SQLCMD_ENCRYPT_FLAG="-N"
  # NOTE: sqlcmd doesn't have an explicit "no encryption" flag like connection strings do;
  # `-No` sets optional, which effectively matches most local scenarios.
  SQLCMD_ENCRYPT_FLAG="-No"
fi

echo "==> Waiting for SQL Server at ${HOST}:${PORT} ..."
for i in $(seq 1 60); do
  if sqlcmd ${SQLCMD_ENCRYPT_FLAG} -S "${HOST},${PORT}" -U "${USER}" -P "${PASSWORD}" -Q "SELECT 1" >/dev/null 2>&1; then
    echo "==> SQL Server is ready."
    exit 0
  fi
  sleep 2
done

echo "ERROR: SQL Server did not become ready in time." >&2
exit 1
