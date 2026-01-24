#!/usr/bin/env bash
set -euo pipefail

#
# .devcontainer/scripts/reset-volumes.sh
#
# Reset SQL Server + Azurite data volumes used by the devcontainer compose stack.
#
# Usage:
#   bash .devcontainer/scripts/reset-volumes.sh
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_FILE=".devcontainer/docker-compose.yml"

sql_container_id="$(docker compose -f "${COMPOSE_FILE}" ps -q sql || true)"
if [[ -z "${sql_container_id}" ]]; then
  echo "No devcontainer SQL container found. Start the devcontainer once, then retry." >&2
  exit 1
fi

project_name="$(docker inspect -f '{{ index .Config.Labels \"com.docker.compose.project\" }}' "${sql_container_id}")"
if [[ -z "${project_name}" ]]; then
  echo "Could not resolve compose project name from SQL container." >&2
  exit 1
fi

sql_volume="${project_name}_ade_sql_data"
azurite_volume="${project_name}_ade_azurite_data"

echo "Removing volumes:"
echo "  - ${sql_volume}"
echo "  - ${azurite_volume}"

docker volume rm "${sql_volume}" "${azurite_volume}"
echo "Done."
