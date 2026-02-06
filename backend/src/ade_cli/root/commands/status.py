"""`ade status` command."""

from __future__ import annotations

import typer

from .. import shared


def register(app: typer.Typer) -> None:
    @app.command(name="status", help="Show tracked ADE service process status.")
    def status() -> None:
        state = shared._load_state()
        if not state:
            typer.echo("ADE status: no tracked services.")
            return

        live = shared._extract_live_service_pids(state)
        mode = state.get("mode", "unknown")
        started_at = state.get("started_at", "unknown")
        services = state.get("services") or []

        typer.echo("ADE status:")
        typer.echo(f"  mode: {mode}")
        typer.echo(f"  started_at: {started_at}")
        typer.echo(f"  services: {','.join(str(item) for item in services)}")

        process_map = state.get("processes") if isinstance(state.get("processes"), dict) else {}
        for service in shared.SERVICE_ORDER:
            if service not in process_map:
                continue
            payload = process_map.get(service)
            if not isinstance(payload, dict):
                continue
            pid = payload.get("pid")
            if not isinstance(pid, int):
                continue
            label = "running" if service in live else "exited"
            typer.echo(f"  {service}: pid={pid} {label}")
