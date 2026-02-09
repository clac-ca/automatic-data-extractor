"""Shared helpers for ADE CLI command modules."""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import typer


@dataclass(frozen=True)
class ManagedProcess:
    name: str
    command: list[str]
    env: dict[str, str] | None = None


def run(
    command: Iterable[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    cmd_list = list(command)
    typer.echo(f"-> {' '.join(cmd_list)}", err=True)
    completed = subprocess.run(cmd_list, cwd=cwd, env=env, check=False)
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


def require_command(
    command: str,
    *,
    friendly_name: str | None = None,
    fix_hint: str | None = None,
) -> str:
    friendly = friendly_name or command
    found = shutil.which(command)
    if found:
        return found

    hint = fix_hint or "Ensure the command is installed and available on PATH."
    typer.echo(f"error: {friendly} not found (looked for `{command}`).\n{hint}", err=True)
    raise typer.Exit(code=1)


def run_many(processes: list[ManagedProcess], *, cwd: Path) -> None:
    if not processes:
        typer.echo("No processes selected.", err=True)
        return

    children: dict[str, subprocess.Popen[str]] = {}

    def _terminate_all() -> None:
        for child in children.values():
            if child.poll() is None:
                child.terminate()

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if all(child.poll() is not None for child in children.values()):
                return
            time.sleep(0.1)

        for name, child in children.items():
            if child.poll() is None:
                typer.echo(f"warning: force-killing {name} (pid {child.pid})", err=True)
                child.kill()

    try:
        for proc in processes:
            typer.echo(f"-> {' '.join(proc.command)}", err=True)
            children[proc.name] = subprocess.Popen(
                proc.command,
                cwd=cwd,
                env=proc.env,
                text=True,
            )

        while True:
            for name, child in children.items():
                code = child.poll()
                if code is None:
                    continue
                typer.echo(f"warning: {name} exited with code {code}", err=True)
                _terminate_all()
                raise typer.Exit(code=code)
            time.sleep(0.2)
    except KeyboardInterrupt:
        _terminate_all()
        raise typer.Exit(code=130) from None


class TestSuite(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    ALL = "all"


def parse_test_suite(value: str | None) -> TestSuite:
    if value is None:
        return TestSuite.UNIT
    normalized = value.strip().lower()
    if normalized in {"unit", "u"}:
        return TestSuite.UNIT
    if normalized in {"integration", "int", "i"}:
        return TestSuite.INTEGRATION
    if normalized in {"all", "a"}:
        return TestSuite.ALL
    typer.echo("error: unknown test suite (use unit, integration, or all).", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "ManagedProcess",
    "TestSuite",
    "parse_test_suite",
    "require_command",
    "run",
    "run_many",
]

