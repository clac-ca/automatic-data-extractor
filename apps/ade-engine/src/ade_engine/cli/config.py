"""Config package commands for the ADE CLI."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path
from typing import Optional

import typer
from typer import BadParameter

from ade_engine.engine import Engine
from ade_engine.exceptions import ConfigError
from ade_engine.logging import create_run_logger_context
from ade_engine.settings import Settings

from .common import (
    LogFormat,
    CONFIG_PACKAGE_OPTION,
    DEBUG_OPTION,
    LOG_FORMAT_OPTION,
    LOG_LEVEL_OPTION,
    QUIET_OPTION,
    resolve_config_package,
    resolve_logging,
)

app = typer.Typer(
    help="Create and validate ADE config packages.",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("init")
def init_config(
    target_dir: Path = typer.Argument(
        ...,
        help="Directory to create the config package in (will be created if missing).",
    ),
    layout: str = typer.Option(
        "src",
        "--layout",
        case_sensitive=False,
        help="Layout to generate: 'src' (recommended) or 'flat'.",
    ),
    package_name: str = typer.Option(
        "ade_config",
        "--package-name",
        help="Python package name to generate (default: ade_config).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow writing into an existing non-empty directory.",
    ),
) -> None:
    """Create a starter ADE config package."""

    if not package_name.isidentifier():
        raise BadParameter(f"--package-name must be a valid Python identifier: {package_name}")

    target_dir = target_dir.expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if any(target_dir.iterdir()) and not force:
        raise BadParameter(f"Target directory is not empty: {target_dir} (use --force to proceed)")

    layout_norm = layout.lower().strip()
    if layout_norm not in {"src", "flat"}:
        raise BadParameter("--layout must be one of: src, flat", param_hint="layout")

    # Copy template package tree from bundled templates
    template_root = resources.files("ade_engine.templates.config_packages.default")
    with resources.as_file(template_root) as template_path:
        shutil.copytree(template_path, target_dir, dirs_exist_ok=True)

    # Adjust package name and layout
    src_pkg_dir = target_dir / "src" / "ade_config"
    if layout_norm == "flat":
        dest_pkg_dir = target_dir / package_name
        dest_pkg_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_pkg_dir), dest_pkg_dir)
        shutil.rmtree(target_dir / "src", ignore_errors=True)
        pkg_path_for_pyproject = package_name
    else:
        dest_pkg_dir = target_dir / "src" / package_name
        if dest_pkg_dir != src_pkg_dir:
            dest_pkg_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_pkg_dir), dest_pkg_dir)
        pkg_path_for_pyproject = f"src/{package_name}"

    # Patch pyproject.toml
    pyproject_path = target_dir / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8") if pyproject_path.exists() else ""
    if text:
        text = text.replace("ade-config-template", package_name)
        text = text.replace("src/ade_config", pkg_path_for_pyproject)
        # If flattened, the hatch target should point to the flat package
        if layout_norm == "flat":
            text = text.replace("packages = [\"src/" + package_name + "\"]", f"packages = [\"{package_name}\"]")
    else:
        text = (
            "[project]\n"
            f"name = \"{package_name}\"\n"
            "version = \"0.1.0\"\n"
            "description = \"ADE config package\"\n"
            "requires-python = \">=3.10\"\n\n"
            "[build-system]\n"
            "requires = [\"setuptools>=64\"]\n"
            "build-backend = \"setuptools.build_meta\"\n\n"
            "[tool.hatch.build.targets.wheel]\n"
            f"packages = [\"{pkg_path_for_pyproject}\"]\n"
        )
    pyproject_path.write_text(text, encoding="utf-8")

    typer.echo(f"Created config package scaffold at: {target_dir}")


@app.command("validate")
def validate_config(
    log_format: Optional[LogFormat] = LOG_FORMAT_OPTION,
    log_level: Optional[str] = LOG_LEVEL_OPTION,
    debug: bool = DEBUG_OPTION,
    quiet: bool = QUIET_OPTION,
    config_package: Optional[Path] = CONFIG_PACKAGE_OPTION,
) -> None:
    """Validate that a config package can be imported and registered."""

    settings = Settings()
    config_path = resolve_config_package(config_package, settings)
    effective_format, effective_level = resolve_logging(
        log_format=log_format,
        log_level=log_level,
        debug=debug,
        quiet=quiet,
        settings=settings,
    )

    engine_settings = settings.model_copy(update={"log_format": effective_format, "log_level": effective_level})
    engine = Engine(settings=engine_settings)

    try:
        with create_run_logger_context(
            log_format=effective_format,
            log_level=effective_level,
            log_file=None,
        ) as log_ctx:
            registry = engine._load_registry(config_package=config_path, logger=log_ctx.logger)
    except (ConfigError, ModuleNotFoundError) as exc:
        typer.echo(f"Config package INVALID: {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:  # pragma: no cover - defensive
        typer.echo(f"Config package validation failed: {exc}")
        raise typer.Exit(code=1)

    typer.echo("Config package OK")
    typer.echo(f"- path: {config_path}")
    typer.echo(f"- fields: {len(registry.fields)}")
    typer.echo(f"- row_detectors: {len(registry.row_detectors)}")
    typer.echo(f"- column_detectors: {len(registry.column_detectors)}")
    typer.echo(f"- column_transforms: {len(registry.column_transforms)}")
    typer.echo(f"- column_validators: {len(registry.column_validators)}")
    typer.echo(f"- hooks: {sum(len(v) for v in registry.hooks.values())}")


__all__ = ["app"]
