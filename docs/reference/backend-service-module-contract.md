# Backend Service Module Contract

## Purpose

Keep backend packages consistent and minimal so each service looks and behaves the same.

## Applies To

Service packages under `backend/src/` that own runtime behavior:

- `ade_api`
- `ade_worker`
- `ade_db`
- `ade_storage`

Shared backend modules in `backend/src/settings.py` and `backend/src/paths.py` provide cross-service infrastructure.

## Required Files

Each service package should include:

- `settings.py`
  - owns service settings model
  - uses `settings.ade_settings_config(...)`
  - exports `Settings`, `get_settings`, `reload_settings`
- `__main__.py`
  - tiny module entrypoint for `python -m <service>`
  - defines `main()` and calls the matching command app in `ade_cli`

## Settings Rules

- Keep one settings class per service package.
- Compose from shared mixins in `settings`.
- Keep cross-package setting contracts in `settings` protocols.
- Only override `ade_settings_config(...)` options when the service requires it.

## CLI Rules

- Canonical command modules live in `ade_cli/`:
  - `ade_cli/api.py`
  - `ade_cli/worker.py`
  - `ade_cli/db.py`
  - `ade_cli/storage.py`
  - `ade_cli/web.py`
- Shared CLI helpers live in `ade_cli/common.py`.
- `ade_cli/main.py` mounts these command apps and owns root orchestration commands (`start`, `dev`, `test`, `reset`).

## Import Boundaries

- Service packages may import shared modules (`settings`, `paths`) plus `ade_db` and `ade_storage` APIs as needed.
- Keep orchestration and command wiring in `ade_cli/`.

## Minimal Templates

### `settings.py`

```python
from pydantic_settings import BaseSettings
from settings import ade_settings_config, create_settings_accessors


class Settings(BaseSettings):
    model_config = ade_settings_config()


get_settings, reload_settings = create_settings_accessors(Settings)
```

### `ade_cli/api.py`

```python
import typer

app = typer.Typer(add_completion=False, invoke_without_command=True)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
```

### `__main__.py`

```python
from ade_cli.api import app as cli_app


def main() -> None:
    cli_app()


if __name__ == "__main__":
    main()
```
