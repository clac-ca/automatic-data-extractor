#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

require_fixed() {
  local file="$1"
  local pattern="$2"
  if ! rg -q --fixed-strings "$pattern" "$file"; then
    echo "error: expected pattern not found in $file" >&2
    echo "missing: $pattern" >&2
    exit 1
  fi
}

# Compose defaults (local)
require_fixed "docker-compose.yaml" 'ADE_API_PROCESSES: ${ADE_API_PROCESSES:-2}'
require_fixed "docker-compose.yaml" 'ADE_WORKER_RUN_CONCURRENCY: ${ADE_WORKER_RUN_CONCURRENCY:-8}'

# Compose defaults (prod)
require_fixed "docker-compose.prod.yaml" 'ADE_API_PROCESSES: ${ADE_API_PROCESSES:-2}'
require_fixed "docker-compose.prod.yaml" 'ADE_WORKER_RUN_CONCURRENCY: ${ADE_WORKER_RUN_CONCURRENCY:-4}'
require_fixed "docker-compose.prod.split.yaml" 'ADE_API_PROCESSES: ${ADE_API_PROCESSES:-2}'
require_fixed "docker-compose.prod.split.yaml" 'ADE_WORKER_RUN_CONCURRENCY: ${ADE_WORKER_RUN_CONCURRENCY:-4}'

# .env.example references
require_fixed ".env.example" '# ADE_API_PROCESSES=2'
require_fixed ".env.example" '# ADE_WORKER_RUN_CONCURRENCY=8'
require_fixed ".env.example" '# ADE_API_PROXY_HEADERS_ENABLED=true'
require_fixed ".env.example" '# ADE_API_FORWARDED_ALLOW_IPS=127.0.0.1'
require_fixed ".env.example" '# ADE_API_THREADPOOL_TOKENS=40'

# Docs matrix should stay aligned with runtime/compose defaults.
require_fixed "docs/reference/defaults-matrix.md" '| `ADE_API_PROCESSES` | `1` | `2` | `2` | `2` |'
require_fixed "docs/reference/defaults-matrix.md" '| `ADE_WORKER_RUN_CONCURRENCY` | `2` | `8` | `4` | `4` |'
require_fixed "docs/reference/defaults-matrix.md" '| `ADE_AUTH_DISABLED` | `false` | `true` | `false` | `false` |'
require_fixed "docs/reference/defaults-matrix.md" '| `ADE_API_PROXY_HEADERS_ENABLED` | `true` | inherited app default | inherited app default | inherited app default |'
require_fixed "docs/reference/defaults-matrix.md" '| `ADE_API_FORWARDED_ALLOW_IPS` | `127.0.0.1` | inherited app default | inherited app default | inherited app default |'
require_fixed "docs/reference/defaults-matrix.md" '| `ADE_API_THREADPOOL_TOKENS` | `40` | inherited app default | inherited app default | inherited app default |'

echo "defaults matrix check: OK"
