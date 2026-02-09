"""Root ADE CLI delegating to service CLIs."""

from __future__ import annotations

import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import urlopen

import typer

from ade_api import cli as api_cli
from ade_api.commands import common
from ade_api.commands import tests as api_tests
from ade_api.commands.migrate import run_migrate
from ade_api.settings import Settings

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE root CLI (start/dev/test/api/worker/web).",
)

_SERVICE_NAMES = {"api", "worker", "web"}


def _has_dev_deps() -> bool:
    return importlib.util.find_spec("pytest") is not None


def _parse_test_suite(value: str | None) -> api_tests.TestSuite:
    return api_tests.parse_suite(value)


def _prepare_env() -> dict[str, str]:
    env = common.build_env()
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{python_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def _register_worker(app: typer.Typer) -> None:
    try:
        from ade_worker import cli as worker_cli
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"ℹ️  ade-worker not available: {exc}", err=True)
        return

    app.add_typer(worker_cli.app, name="worker")


def _parse_services(value: str | None) -> set[str]:
    if value is None or value.strip() == "":
        return set(_SERVICE_NAMES)
    raw = value.strip().lower()
    if raw in {"all", "*"}:
        return set(_SERVICE_NAMES)
    parts = [item.strip().lower() for item in value.replace(",", " ").split() if item.strip()]
    services = set(parts)
    invalid = sorted(services - _SERVICE_NAMES)
    if invalid:
        typer.echo(
            "❌ Unknown services: "
            + ", ".join(invalid)
            + ". Use: api, worker, web.",
            err=True,
        )
        raise typer.Exit(code=1)
    if not services:
        typer.echo("❌ No services selected for ade start.", err=True)
        raise typer.Exit(code=1)
    return services


def _repo_root() -> Path | None:
    root = common.REPO_ROOT
    web_dir = root / "apps" / "ade-web"
    if (web_dir / "package.json").is_file():
        return root
    return None


def _run_web(script: str) -> None:
    root = _repo_root()
    if root is None:
        typer.echo("❌ Web commands require the repo checkout (apps/ade-web).", err=True)
        raise typer.Exit(code=1)

    web_dir = root / "apps" / "ade-web"
    common.ensure_node_modules(web_dir)
    npm_bin = common.npm_path()
    common.run([npm_bin, "run", script], cwd=web_dir)


def _resolve_web_dist_dir(dist_dir: Path | None) -> Path:
    if dist_dir is None:
        env_value = os.getenv("ADE_WEB_DIST_DIR")
        if env_value:
            dist_dir = Path(env_value)

    candidates: list[Path] = []
    if dist_dir is not None:
        candidates.append(dist_dir)
    candidates.append(Path("/app/web/dist"))
    candidates.append(common.REPO_ROOT / "apps" / "ade-web" / "dist")

    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved.is_dir() and (resolved / "index.html").is_file():
            return resolved

    typer.echo(
        "❌ Web dist directory not found. Build the web app first "
        "(run `ade web build` or `npm run build` in apps/ade-web).",
        err=True,
    )
    raise typer.Exit(code=1)


def _normalize_proxy_target(value: str) -> str:
    target = value.strip()
    if not target:
        raise ValueError("proxy target cannot be empty")
    target = target.rstrip("/")
    if target.endswith("/api"):
        target = target[: -len("/api")]
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("proxy target must be a full http(s) URL (e.g., http://api:8000)")
    return target


def _default_proxy_target(host: str, port: int) -> str:
    resolved_host = host
    if host in {"0.0.0.0", "::"}:
        resolved_host = "127.0.0.1"
    return f"http://{resolved_host}:{port}"


def _nginx_command(
    *,
    dist_dir: Path,
    port: int,
    proxy_target: str,
) -> tuple[list[str], Path]:
    runtime_dir = Path(tempfile.mkdtemp(prefix="ade-nginx-"))
    temp_dir = runtime_dir / "temp"
    for name in ["client_body", "proxy", "fastcgi", "uwsgi", "scgi"]:
        (temp_dir / name).mkdir(parents=True, exist_ok=True)

    config_path = runtime_dir / "nginx.conf"
    dist_root = dist_dir.resolve()
    temp_root = temp_dir.resolve()
    config_body = textwrap.dedent(
        f"""
        worker_processes  1;
        error_log /dev/stderr info;
        pid {runtime_dir}/nginx.pid;

        events {{
            worker_connections 1024;
        }}

        http {{
            include /etc/nginx/mime.types;
            default_type application/octet-stream;
            access_log /dev/stdout;

            sendfile on;
            keepalive_timeout 65;

            client_body_temp_path {temp_root}/client_body;
            proxy_temp_path {temp_root}/proxy;
            fastcgi_temp_path {temp_root}/fastcgi;
            uwsgi_temp_path {temp_root}/uwsgi;
            scgi_temp_path {temp_root}/scgi;

            map $http_upgrade $connection_upgrade {{
                default upgrade;
                '' close;
            }}

            server {{
                listen {port};
                server_name _;

                root {dist_root};
                index index.html;

                location /api/ {{
                    proxy_pass {proxy_target};
                    proxy_http_version 1.1;
                    proxy_set_header Host $host;
                    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                    proxy_set_header X-Forwarded-Proto $scheme;
                    proxy_set_header Upgrade $http_upgrade;
                    proxy_set_header Connection $connection_upgrade;
                }}

                location /assets/ {{
                    try_files $uri =404;
                    add_header Cache-Control "public, max-age=31536000, immutable";
                }}

                location / {{
                    try_files $uri /index.html;
                }}
            }}
        }}
        """
    ).lstrip()
    config_path.write_text(config_body, encoding="utf-8")

    nginx_bin = common.require_command(
        "nginx",
        friendly_name="nginx",
        fix_hint="Install nginx or use `ade web dev` during development.",
    )
    cmd = [nginx_bin, "-c", str(config_path), "-g", "daemon off;"]
    return cmd, runtime_dir


def _run_nginx(
    *,
    dist_dir: Path,
    port: int,
    proxy_target: str,
) -> None:
    cmd, runtime_dir = _nginx_command(
        dist_dir=dist_dir,
        port=port,
        proxy_target=proxy_target,
    )
    try:
        typer.echo(f"🌐 Web server: http://0.0.0.0:{port}")
        common.run(cmd, cwd=None)
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)


def _register_web(app: typer.Typer, *, dev_available: bool) -> None:
    web_app = typer.Typer(add_completion=False, help="ADE web commands.")

    @web_app.command(name="serve", help="Serve the built web app via nginx.")
    def serve(
        port: int = typer.Option(
            8000,
            "--port",
            help="Port for the web server.",
            min=1,
            max=65535,
            envvar="ADE_WEB_PORT",
        ),
        proxy_target: str = typer.Option(
            None,
            "--proxy-target",
            help="Base URL for the API (e.g., http://api:8000).",
            envvar="ADE_WEB_PROXY_TARGET",
        ),
        dist_dir: Path = typer.Option(
            None,
            "--dist-dir",
            help="Directory with built web assets (defaults to /app/web/dist).",
            envvar="ADE_WEB_DIST_DIR",
        ),
    ) -> None:
        resolved_dist = _resolve_web_dist_dir(dist_dir)
        resolved_proxy = proxy_target or "http://127.0.0.1:8000"
        try:
            resolved_proxy = _normalize_proxy_target(resolved_proxy)
        except ValueError as exc:
            typer.echo(f"❌ {exc}", err=True)
            raise typer.Exit(code=1)
        _run_nginx(dist_dir=resolved_dist, port=port, proxy_target=resolved_proxy)

    if dev_available:

        @web_app.command(name="dev", help="Run the web dev server (Vite).")
        def dev() -> None:
            _run_web("dev")

        @web_app.command(name="build", help="Build the web app.")
        def build() -> None:
            _run_web("build")

        @web_app.command(name="test", help="Run web tests.")
        def test() -> None:
            _run_web("test")

        @web_app.command(name="lint", help="Run web linting.")
        def lint() -> None:
            _run_web("lint")

    app.add_typer(web_app, name="web")


def _api_command(
    *,
    host: str,
    port: int,
    workers: int,
    reload: bool,
) -> list[str]:
    uvicorn_bin = common.uvicorn_path()
    cmd = [uvicorn_bin, "ade_api.main:app", "--host", host, "--port", str(port)]
    if reload:
        if workers > 1:
            typer.echo("Note: API workers > 1; disabling reload in dev.")
            cmd.extend(["--workers", str(workers)])
        else:
            cmd.extend(["--reload", "--reload-dir", "apps/ade-api"])
    elif workers > 1:
        cmd.extend(["--workers", str(workers)])
    return cmd


def _worker_command(*, dev: bool) -> list[str]:
    return [sys.executable, "-m", "ade_worker.cli", "dev" if dev else "start"]


def _terminate(proc: subprocess.Popen, *, name: str) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:  # noqa: BLE001
        proc.kill()
    typer.echo(f"🛑 stopped {name}")


def _run_stack(
    commands: dict[str, tuple[list[str], Path | None]],
    *,
    env: dict[str, str],
    on_ready: Callable[[dict[str, subprocess.Popen]], dict[str, tuple[list[str], Path | None]] | None]
    | None = None,
) -> None:
    procs: dict[str, subprocess.Popen] = {}
    for name, (cmd, cwd) in commands.items():
        typer.echo(f"▶️  starting {name}: {' '.join(cmd)}")
        procs[name] = subprocess.Popen(cmd, cwd=cwd, env=env)

    if on_ready is not None:
        try:
            extra = on_ready(procs)
        except Exception:  # noqa: BLE001
            for name, proc in procs.items():
                _terminate(proc, name=name)
            raise
        if extra:
            for name, (cmd, cwd) in extra.items():
                if name in procs:
                    typer.echo(f"❌ Duplicate service name: {name}", err=True)
                    for other_name, other_proc in procs.items():
                        _terminate(other_proc, name=other_name)
                    raise typer.Exit(code=1)
                typer.echo(f"▶️  starting {name}: {' '.join(cmd)}")
                procs[name] = subprocess.Popen(cmd, cwd=cwd, env=env)

    def _shutdown(signum: int, _frame) -> None:  # type: ignore[override]
        typer.echo(f"🛑 received signal {signum}; stopping...")
        for name, proc in procs.items():
            _terminate(proc, name=name)
        raise typer.Exit(code=0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        while True:
            for name, proc in procs.items():
                code = proc.poll()
                if code is not None:
                    typer.echo(f"⚠️  {name} exited with code {code}", err=True)
                    for other_name, other_proc in procs.items():
                        if other_name != name:
                            _terminate(other_proc, name=other_name)
                    raise typer.Exit(code=code)
            time.sleep(0.5)
    finally:
        for name, proc in procs.items():
            _terminate(proc, name=name)


def _wait_for_api(
    *,
    url: str,
    api_proc: subprocess.Popen | None,
    timeout_seconds: float,
    interval_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if api_proc is not None and api_proc.poll() is not None:
            raise RuntimeError("API process exited before it became ready.")
        try:
            with urlopen(url, timeout=5) as response:
                if 200 <= response.status < 300:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(interval_seconds)
    if last_error:
        raise RuntimeError(f"API health check failed: {last_error}")
    raise RuntimeError("API health check timed out.")


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


app.add_typer(api_cli.app, name="api")
_register_worker(app)


@app.command(name="test", help="Run ADE tests (API + worker + web).")
def test(
    suite: str | None = typer.Argument(
        None,
        help="Suite to run for API/worker: unit, integration, or all (default: unit).",
    ),
) -> None:
    resolved_suite = _parse_test_suite(suite)
    api_tests.run_tests(resolved_suite)

    try:
        from ade_worker import cli as worker_cli
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"ℹ️  ade-worker not available: {exc}", err=True)
    else:
        if hasattr(worker_cli, "run_tests") and hasattr(worker_cli, "parse_suite"):
            worker_cli.run_tests(worker_cli.parse_suite(suite))
        else:
            typer.echo("ℹ️  ade-worker test command not available.", err=True)

    _run_web("test")

@app.command(name="start", help="Start API + worker + web (nginx).")
def start(
    host: str = typer.Option(
        None,
        "--host",
        help="Host/interface for the API server.",
        envvar="ADE_API_HOST",
    ),
    port: int = typer.Option(
        None,
        "--port",
        help="Port for the API server.",
        envvar="ADE_API_PORT",
    ),
    workers: int = typer.Option(
        None,
        "--workers",
        help="Number of API worker processes.",
        envvar="ADE_API_WORKERS",
        min=1,
    ),
    services: str = typer.Option(
        None,
        "--services",
        help="Comma-separated list of services to start (api, worker, web).",
        envvar="ADE_START_SERVICES",
    ),
    web_port: int = typer.Option(
        8000,
        "--web-port",
        help="Port for the web server.",
        min=1,
        max=65535,
        envvar="ADE_WEB_PORT",
    ),
    web_proxy_target: str = typer.Option(
        None,
        "--web-proxy-target",
        help="Base URL for the API (e.g., http://api:8000).",
        envvar="ADE_WEB_PROXY_TARGET",
    ),
    web_dist_dir: Path = typer.Option(
        None,
        "--web-dist-dir",
        help="Directory with built web assets (defaults to /app/web/dist).",
        envvar="ADE_WEB_DIST_DIR",
    ),
) -> None:
    selected = _parse_services(services)
    env = _prepare_env()

    repo_root = common.REPO_ROOT
    cwd = repo_root if repo_root.exists() else None

    commands: dict[str, tuple[list[str], Path | None]] = {}
    nginx_runtime_dir: Path | None = None

    resolved_host = host or "0.0.0.0"
    resolved_port = None
    resolved_workers = 1
    deferred_commands: dict[str, tuple[list[str], Path | None]] = {}

    if "api" in selected:
        settings = Settings()
        resolved_host = host or (settings.api_host or "0.0.0.0")
        default_port = 8001 if "web" in selected else 8000
        resolved_port = int(port if port is not None else (settings.api_port or default_port))
        resolved_workers = int(workers if workers is not None else (settings.api_workers or 1))

        if "web" in selected and resolved_port == web_port:
            typer.echo(
                "❌ API port conflicts with web port. "
                "Set ADE_API_PORT or ADE_WEB_PORT to different values.",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo("🗄️  Running migrations…")
        run_migrate()

        api_cmd = _api_command(
            host=resolved_host,
            port=resolved_port,
            workers=resolved_workers,
            reload=False,
        )
        commands["api"] = (api_cmd, cwd)

    if "worker" in selected:
        worker_cmd = _worker_command(dev=False)
        commands["worker"] = (worker_cmd, cwd)

    if "web" in selected:
        resolved_dist = _resolve_web_dist_dir(web_dist_dir)
        proxy_target = web_proxy_target
        if not proxy_target and "api" in selected and resolved_port is not None:
            proxy_target = _default_proxy_target(resolved_host, resolved_port)
        if not proxy_target:
            typer.echo(
                "❌ Web proxy target is required when the API is not started "
                "(set ADE_WEB_PROXY_TARGET).",
                err=True,
            )
            raise typer.Exit(code=1)
        try:
            proxy_target = _normalize_proxy_target(proxy_target)
        except ValueError as exc:
            typer.echo(f"❌ {exc}", err=True)
            raise typer.Exit(code=1)

        web_cmd, nginx_runtime_dir = _nginx_command(
            dist_dir=resolved_dist,
            port=web_port,
            proxy_target=proxy_target,
        )
        if "api" in selected:
            deferred_commands["web"] = (web_cmd, cwd)
        else:
            commands["web"] = (web_cmd, cwd)

    try:
        health_timeout = float(os.getenv("ADE_WEB_WAIT_TIMEOUT", "60"))
        health_interval = float(os.getenv("ADE_WEB_WAIT_INTERVAL", "0.5"))
        health_url = None
        if "api" in selected and deferred_commands:
            health_url = f"{proxy_target}/api/v1/health"

        def _on_ready(procs: dict[str, subprocess.Popen]) -> dict[str, tuple[list[str], Path | None]] | None:
            if not deferred_commands:
                return None
            if health_url:
                typer.echo("⏳ Waiting for API before starting web...")
                _wait_for_api(
                    url=health_url,
                    api_proc=procs.get("api"),
                    timeout_seconds=health_timeout,
                    interval_seconds=health_interval,
                )
            return deferred_commands

        _run_stack(commands, env=env, on_ready=_on_ready if deferred_commands else None)
    finally:
        if nginx_runtime_dir is not None:
            shutil.rmtree(nginx_runtime_dir, ignore_errors=True)


def _register_dev(app: typer.Typer) -> None:
    @app.command(name="dev", help="Start API + worker + web in dev mode (reload).")
    def dev(
        host: str = typer.Option(
            None,
            "--host",
            help="Host/interface for the API dev server.",
            envvar="ADE_API_HOST",
        ),
        port: int = typer.Option(
            None,
            "--port",
            help="Port for the API dev server.",
            envvar="ADE_API_PORT",
        ),
        workers: int = typer.Option(
            None,
            "--workers",
            help="Number of API worker processes.",
            envvar="ADE_API_WORKERS",
            min=1,
        ),
    ) -> None:
        root = _repo_root()
        if root is None:
            typer.echo("❌ ade dev requires the repo checkout (apps/ade-web).", err=True)
            raise typer.Exit(code=1)

        env = _prepare_env()

        settings = Settings()
        resolved_port = int(port if port is not None else (settings.api_port or 8000))
        resolved_host = host or (settings.api_host or "0.0.0.0")
        resolved_workers = int(workers if workers is not None else (settings.api_workers or 1))

        typer.echo("🗄️  Running migrations…")
        run_migrate()

        api_cmd = _api_command(
            host=resolved_host,
            port=resolved_port,
            workers=resolved_workers,
            reload=True,
        )
        worker_cmd = _worker_command(dev=True)

        web_dir = root / "apps" / "ade-web"
        common.ensure_node_modules(web_dir)
        npm_bin = common.npm_path()
        web_cmd = [npm_bin, "run", "dev"]

        _run_stack(
            {
                "api": (api_cmd, root),
                "worker": (worker_cmd, root),
                "web": (web_cmd, web_dir),
            },
            env=env,
        )


_dev_available = _has_dev_deps()
_register_web(app, dev_available=_dev_available)
if _dev_available:
    _register_dev(app)


if __name__ == "__main__":
    app()
