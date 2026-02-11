# ADE Backend

## Purpose

Describe the backend package boundary that ships API, worker, and shared
runtime packages together.

## Definitions

- `ade`: unified backend CLI entrypoint.
- `ade_api`: control-plane HTTP service.
- `ade_worker`: run execution data plane.
- `ade_db`: shared schema and migrations package.
- `ade_storage`: shared blob/storage integration package.

## Facts

| Area | Location | Notes |
| --- | --- | --- |
| Python source root | `backend/src/` | unified backend package tree |
| Main services | `ade_api`, `ade_worker` | launched via `uv run ade ...` |
| Shared packages | `ade_db`, `ade_storage` | imported by both services |
| Unified tests | `backend/tests/` | API + worker + integration suites |

## Examples

```bash
cd backend
uv run ade dev
uv run ade test
```
