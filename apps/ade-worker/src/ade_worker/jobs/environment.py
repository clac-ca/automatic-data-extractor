"""Environment provisioning job."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session, sessionmaker

from ..paths import PathManager
from ..queue import EnvironmentClaim, EnvironmentQueue
from ..repo import Repo
from ..settings import Settings
from ..subprocess_runner import EventLog, SubprocessRunner

logger = logging.getLogger("ade_worker")


def utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=None)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _run_capture_text(cmd: list[str]) -> str:
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    return out or err


@dataclass(slots=True)
class EnvironmentJob:
    settings: Settings
    SessionLocal: sessionmaker[Session]
    queue: EnvironmentQueue
    repo: Repo
    paths: PathManager
    runner: SubprocessRunner
    worker_id: str

    def _install_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["UV_CACHE_DIR"] = str(self.paths.pip_cache_dir())
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _uv_bin(self) -> str:
        uv_bin = shutil.which("uv")
        if not uv_bin:
            raise RuntimeError("uv not found on PATH; install ade-worker dependencies with uv available")
        return uv_bin

    def _heartbeat_env(self, env: EnvironmentClaim) -> None:
        self.queue.heartbeat(
            env_id=env.id,
            worker_id=self.worker_id,
            now=utcnow(),
            lease_seconds=int(self.settings.worker_lease_seconds),
        )

    def process(self, claim: EnvironmentClaim) -> None:
        env = self.repo.load_environment(claim.id)
        if not env:
            logger.error("environment not found: %s", claim.id)
            return

        workspace_id = str(env["workspace_id"])
        configuration_id = str(env["configuration_id"])
        deps_digest = str(env["deps_digest"])
        engine_spec = str(env.get("engine_spec") or self.settings.engine_spec)

        env_root = self.paths.environment_root(
            workspace_id,
            configuration_id,
            deps_digest,
            claim.id,
        )
        venv_dir = self.paths.environment_venv_dir(
            workspace_id,
            configuration_id,
            deps_digest,
            claim.id,
        )
        event_log = EventLog(
            self.paths.environment_event_log_path(
                workspace_id,
                configuration_id,
                deps_digest,
                claim.id,
            )
        )
        ctx = {
            "environment_id": claim.id,
            "workspace_id": workspace_id,
            "configuration_id": configuration_id,
            "deps_digest": deps_digest,
        }

        if env_root.exists():
            shutil.rmtree(env_root, ignore_errors=True)
        _ensure_dir(env_root)

        event_log.emit(event="environment.start", message="Starting environment build", context=ctx)

        deadline = time.monotonic() + float(self.settings.worker_env_build_timeout_seconds)
        install_env = self._install_env()
        uv_bin = self._uv_bin()
        last_exit_code: int | None = None

        def remaining() -> float:
            return max(0.1, deadline - time.monotonic())

        try:
            # 1) venv
            create_cmd = [uv_bin, "venv", "--python", sys.executable, str(venv_dir)]
            res = self.runner.run(
                create_cmd,
                event_log=event_log,
                scope="environment.venv",
                timeout_seconds=remaining(),
                cwd=None,
                env=install_env,
                heartbeat=lambda: self._heartbeat_env(claim),
                heartbeat_interval=max(1.0, self.settings.worker_lease_seconds / 3),
                context=ctx,
            )
            last_exit_code = res.exit_code
            if res.exit_code != 0:
                raise RuntimeError(f"venv creation failed (exit {res.exit_code})")

            python_bin = self.paths.python_in_venv(venv_dir)
            if not python_bin.exists():
                raise RuntimeError(f"venv python missing: {python_bin}")

            # 2) install engine
            install_engine = [uv_bin, "pip", "install", "--python", str(python_bin)]
            if Path(str(engine_spec)).exists():
                install_engine.extend(["-e", str(engine_spec)])
            else:
                install_engine.append(str(engine_spec))

            res = self.runner.run(
                install_engine,
                event_log=event_log,
                scope="environment.engine",
                timeout_seconds=remaining(),
                cwd=None,
                env=install_env,
                heartbeat=lambda: self._heartbeat_env(claim),
                heartbeat_interval=max(1.0, self.settings.worker_lease_seconds / 3),
                context=ctx,
            )
            last_exit_code = res.exit_code
            if res.exit_code != 0:
                raise RuntimeError(f"engine install failed (exit {res.exit_code})")

            # 3) install config package (editable)
            config_dir = self.paths.config_package_dir(workspace_id, configuration_id)
            if not config_dir.exists():
                raise RuntimeError(f"config package dir missing: {config_dir}")

            res = self.runner.run(
                [uv_bin, "pip", "install", "--python", str(python_bin), "-e", str(config_dir)],
                event_log=event_log,
                scope="environment.config",
                timeout_seconds=remaining(),
                cwd=None,
                env=install_env,
                heartbeat=lambda: self._heartbeat_env(claim),
                heartbeat_interval=max(1.0, self.settings.worker_lease_seconds / 3),
                context=ctx,
            )
            last_exit_code = res.exit_code
            if res.exit_code != 0:
                raise RuntimeError(f"config install failed (exit {res.exit_code})")

            # 4) probe versions
            python_version = _run_capture_text([str(python_bin), "--version"])
            try:
                engine_version = subprocess.check_output(
                    [str(python_bin), "-c", "import ade_engine; print(getattr(ade_engine, '__version__', 'unknown'))"],
                    text=True,
                ).strip()
            except Exception:
                engine_version = None

            event_log.emit(
                event="environment.versions",
                message=f"python={python_version} engine={engine_version or 'unknown'}",
                context=ctx,
            )

            finished_at = utcnow()
            with self.SessionLocal.begin() as session:
                ok = self.queue.ack_success(
                    session=session,
                    env_id=claim.id,
                    worker_id=self.worker_id,
                    now=finished_at,
                )
                if not ok:
                    event_log.emit(
                        event="environment.lost_claim",
                        level="warning",
                        message="Environment status changed before completion",
                        context=ctx,
                    )
                    return
                self.repo.record_environment_metadata(
                    session=session,
                    env_id=claim.id,
                    now=finished_at,
                    python_interpreter=str(python_bin),
                    python_version=python_version,
                    engine_version=engine_version,
                )

            event_log.emit(event="environment.complete", message="Environment ready", context=ctx)

        except Exception as exc:
            err = str(exc)
            logger.exception("environment build failed: %s", err)

            finished_at = utcnow()
            exit_code = last_exit_code or 1

            with self.SessionLocal.begin() as session:
                ok = self.queue.ack_failure(
                    session=session,
                    env_id=claim.id,
                    worker_id=self.worker_id,
                    now=finished_at,
                    error_message=err,
                )
                if not ok:
                    event_log.emit(
                        event="environment.lost_claim",
                        level="warning",
                        message="Environment status changed before failure ack",
                        context=ctx,
                    )
                    return

                self.repo.record_environment_metadata(
                    session=session,
                    env_id=claim.id,
                    now=finished_at,
                    python_interpreter=None,
                    python_version=None,
                    engine_version=None,
                )

            event_log.emit(
                event="environment.failed",
                level="error",
                message=f"{err} (exit {exit_code})",
                context=ctx,
            )


__all__ = ["EnvironmentJob"]
