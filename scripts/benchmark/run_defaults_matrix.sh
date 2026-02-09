#!/usr/bin/env bash
set -euo pipefail

# Run a small matrix against compose defaults to compare API throughput.
# Optional worker benchmark hook:
#   ADE_BENCHMARK_WORKLOAD_CMD='bash scripts/benchmark/my_worker_benchmark.sh'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Default to local compose so benchmark can run without additional required prod vars.
COMPOSE_FILE="${ADE_BENCHMARK_COMPOSE_FILE:-docker-compose.yaml}"
HEALTH_URL="${ADE_BENCHMARK_HEALTH_URL:-http://localhost:8000/api/v1/health}"
REQUESTS="${ADE_BENCHMARK_REQUESTS:-3000}"
CONCURRENCY="${ADE_BENCHMARK_HTTP_CONCURRENCY:-80}"
API_PROCESSES_LIST="${ADE_BENCHMARK_API_PROCESSES_LIST:-1 2 4}"
WORKER_RUN_CONCURRENCY_LIST="${ADE_BENCHMARK_WORKER_RUN_CONCURRENCY_LIST:-2 4 8}"
RESULTS_FILE="${ADE_BENCHMARK_RESULTS_FILE:-benchmark-defaults-matrix.csv}"

cat > "$RESULTS_FILE" <<CSV
api_processes,worker_run_concurrency,api_benchmark_exit,worker_benchmark_exit
CSV

wait_for_health() {
  local attempts=0
  local max_attempts=60
  until curl -fsS "$HEALTH_URL" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge "$max_attempts" ]; then
      echo "error: health check never passed for $HEALTH_URL" >&2
      return 1
    fi
    sleep 2
  done
}

cleanup() {
  docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
}
trap cleanup EXIT

for api_processes in $API_PROCESSES_LIST; do
  for worker_run_concurrency in $WORKER_RUN_CONCURRENCY_LIST; do
    echo "== matrix: ADE_API_PROCESSES=$api_processes ADE_WORKER_RUN_CONCURRENCY=$worker_run_concurrency =="

    ADE_API_PROCESSES="$api_processes" \
    ADE_WORKER_RUN_CONCURRENCY="$worker_run_concurrency" \
    docker compose -f "$COMPOSE_FILE" up -d --force-recreate

    wait_for_health

    set +e
    python3 scripts/benchmark/api_benchmark.py \
      --url "$HEALTH_URL" \
      --requests "$REQUESTS" \
      --concurrency "$CONCURRENCY"
    api_exit=$?
    set -e

    worker_exit=0
    if [ -n "${ADE_BENCHMARK_WORKLOAD_CMD:-}" ]; then
      echo "-> running worker benchmark hook"
      set +e
      bash -lc "$ADE_BENCHMARK_WORKLOAD_CMD"
      worker_exit=$?
      set -e
    else
      echo "-> worker benchmark hook not set; skipping worker workload test"
    fi

    echo "$api_processes,$worker_run_concurrency,$api_exit,$worker_exit" >> "$RESULTS_FILE"

    docker compose -f "$COMPOSE_FILE" down
  done
done

echo "Matrix results written to $RESULTS_FILE"
