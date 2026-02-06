# Automatic Data Extractor (ADE)

ADE is a self-hosted document normalization platform with:

- FastAPI control plane (`ade-api`)
- Background run processor (`ade-worker`)
- React web UI (`ade-web`)
- Shared DB/storage packages (`ade-db`, `ade-storage`)

## Quickstart (Local)

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor
docker compose up --build -d
```

Open `http://localhost:8000`.

Stop:

```bash
docker compose down
```

Full local reset:

```bash
docker compose down -v
```

## Native Dev Loop (Isolated Per Worktree)

```bash
./setup.sh --with-infra
cd backend && uv run ade dev
```

This flow uses a generated local profile in `.env` and keeps each worktree isolated.

Useful commands:

```bash
cd backend && uv run ade infra info
cd backend && uv run ade infra up -d --wait
cd backend && uv run ade infra down
cd backend && uv run ade infra down -v --rmi all
./setup.sh --with-infra --force
```

## Production Start Points

Primary production path: Azure Container Apps.

- Bootstrap tutorial: [`docs/tutorials/production-bootstrap.md`](docs/tutorials/production-bootstrap.md)
- Deployment runbook: [`docs/how-to/deploy-production.md`](docs/how-to/deploy-production.md)
- Scaling guide: [`docs/how-to/scale-and-tune-throughput.md`](docs/how-to/scale-and-tune-throughput.md)

Self-hosted compose production is still supported, but not the default path.

## Default Performance Settings

Benchmark-backed defaults are now set directly in compose:

- Local (`docker-compose.yaml`)
  - `ADE_API_PROCESSES=2`
  - `ADE_WORKER_RUN_CONCURRENCY=8`
- Self-hosted production (`docker-compose.prod.yaml`, `docker-compose.prod.split.yaml`)
  - `ADE_API_PROCESSES=2`
  - `ADE_WORKER_RUN_CONCURRENCY=4`

These are safe starting points with better out-of-box throughput than app-level defaults.

API runtime hardening defaults (app-level) are also enabled by default:

- `ADE_API_PROXY_HEADERS_ENABLED=true`
- `ADE_API_FORWARDED_ALLOW_IPS=127.0.0.1`
- `ADE_API_THREADPOOL_TOKENS=40`
- `ADE_DATABASE_CONNECTION_BUDGET` unset (warn-only if configured)

## Documentation

Top-level docs index: [`docs/index.md`](docs/index.md)

Primary operator pages:

- [`docs/tutorials/local-quickstart.md`](docs/tutorials/local-quickstart.md)
- [`docs/tutorials/production-bootstrap.md`](docs/tutorials/production-bootstrap.md)
- [`docs/how-to/deploy-production.md`](docs/how-to/deploy-production.md)
- [`docs/troubleshooting/triage-playbook.md`](docs/troubleshooting/triage-playbook.md)

## Contributing

- Use Conventional Commits (`feat:`, `fix:`, `deps:`, `chore:`).
- Run relevant tests/lint before merging.
- Update docs in the same PR when behavior changes.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/standards/documentation-maintenance.md`](docs/standards/documentation-maintenance.md).

## Security Notes

- Treat `ADE_SECRET_KEY` like a password.
- Do not enable `ADE_AUTH_DISABLED=true` in production.
- Restrict network access to Postgres and blob storage endpoints.

## License

The MIT License (MIT)

Copyright (c) 2015 Chris Kibble

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
