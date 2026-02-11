# Defaults Matrix

Use this page as the source of truth for capacity/security defaults across app code and compose files.

Azure Container Apps production deployments should set values explicitly in app
env vars/secrets and not rely on compose defaults.

## Capacity Defaults

| Variable | App Code Default | `docker-compose.yaml` (local) | `docker-compose.prod.yaml` | `docker-compose.prod.split.yaml` |
| --- | --- | --- | --- | --- |
| `ADE_API_PROCESSES` | `1` | `2` | `2` | `2` |
| `ADE_WORKER_RUN_CONCURRENCY` | `2` | `8` | `4` | `4` |

## Security and Runtime Mode Defaults

| Variable | App Code Default | `docker-compose.yaml` (local) | `docker-compose.prod.yaml` | `docker-compose.prod.split.yaml` |
| --- | --- | --- | --- | --- |
| `ADE_AUTH_DISABLED` | `false` | `true` | `false` | `false` |
| `ADE_AUTH_PASSWORD_RESET_ENABLED` | `true` | inherited app default | inherited app default | inherited app default |
| `ADE_AUTH_PASSWORD_MFA_REQUIRED` | `false` | inherited app default | inherited app default | inherited app default |
| `ADE_AUTH_MODE` | `password_only` | inherited app default | inherited app default | inherited app default |
| `ADE_SERVICES` | `api,worker,web` | `api,worker,web` | `api,worker,web` | app=`api,web`, worker=`worker` |

## API Runtime Hardening Defaults

| Variable | App Code Default | `docker-compose.yaml` (local) | `docker-compose.prod.yaml` | `docker-compose.prod.split.yaml` |
| --- | --- | --- | --- | --- |
| `ADE_API_PROXY_HEADERS_ENABLED` | `true` | inherited app default | inherited app default | inherited app default |
| `ADE_API_FORWARDED_ALLOW_IPS` | `127.0.0.1` | inherited app default | inherited app default | inherited app default |
| `ADE_API_THREADPOOL_TOKENS` | `40` | inherited app default | inherited app default | inherited app default |
| `ADE_DATABASE_CONNECTION_BUDGET` | unset | unset | unset | unset |

## Best-Practice Rule

- App code defaults: safe behavior defaults.
- `docker-compose.yaml` defaults: local convenience.
- `.env`: operator overrides and secrets.
- self-hosted production compose: fail fast for required values with `${VAR:?message}`.

## Keep This Matrix Accurate

When updating defaults in app code, `.env.example`, or compose files, update this matrix in the same change.

## Benchmarking Helpers

- API endpoint benchmark: `python3 scripts/benchmark/api_benchmark.py --help`
- Matrix runner (compose + API benchmark + optional worker hook):

```bash
bash scripts/benchmark/run_defaults_matrix.sh
```

By default this uses `docker-compose.yaml`; set `ADE_BENCHMARK_COMPOSE_FILE` to target another compose file.
Use `ADE_BENCHMARK_WORKLOAD_CMD` to plug in your run-processing benchmark command.
