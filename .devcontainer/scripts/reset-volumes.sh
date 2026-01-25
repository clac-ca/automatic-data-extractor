#!/usr/bin/env bash
set -euo pipefail

#
# .devcontainer/scripts/reset-volumes.sh
#
# Reset Postgres + Azurite data volumes used by the devcontainer compose stack.
#
# Usage:
#   bash .devcontainer/scripts/reset-volumes.sh
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_FILE=".devcontainer/docker-compose.yml"

postgres_container_id="$(docker compose -f "${COMPOSE_FILE}" ps -q postgres || true)"
if [[ -z "${postgres_container_id}" ]]; then
  echo "No devcontainer Postgres container found. Start the devcontainer once, then retry." >&2
  exit 1
fi

project_name="$(docker inspect -f '{{ index .Config.Labels \"com.docker.compose.project\" }}' "${postgres_container_id}")"
if [[ -z "${project_name}" ]]; then
  echo "Could not resolve compose project name from Postgres container." >&2
  exit 1
fi

pg_volume="${project_name}_ade_pg_data"
azurite_volume="${project_name}_ade_azurite_data"

echo "Removing volumes:"
echo "  - ${pg_volume}"
echo "  - ${azurite_volume}"

docker volume rm "${pg_volume}" "${azurite_volume}"
echo "Done."
