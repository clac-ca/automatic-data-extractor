"""Init command."""

from __future__ import annotations

from pathlib import Path

import typer

from ade_cli.commands import common


def _ensure_sqlite_parent_dir(url: str) -> None:
    try:
        from sqlalchemy.engine import make_url
    except ModuleNotFoundError:
        return

    try:
        parsed = make_url(url)
    except Exception:
        return
    if parsed.get_backend_name() != "sqlite":
        return
    db = (parsed.database or "").strip()
    if not db or db == ":memory:" or db.startswith("file:"):
        return
    path = Path(db)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)


def _normalize_mssql_url(url, env: dict[str, str]):
    try:
        from sqlalchemy.engine import URL
    except ModuleNotFoundError as exc:
        raise RuntimeError("SQLAlchemy is required to initialize the database.") from exc

    if url.drivername == "mssql":
        url = url.set(drivername="mssql+pyodbc")

    query = dict(url.query or {})
    present = {k.lower() for k in query}

    def _setdefault_ci(key: str, value: str | None) -> None:
        if value and key.lower() not in present:
            query[key] = value
            present.add(key.lower())

    _setdefault_ci("driver", "ODBC Driver 18 for SQL Server")
    _setdefault_ci("Encrypt", env.get("ADE_SQL_ENCRYPT", "optional"))
    _setdefault_ci("TrustServerCertificate", env.get("ADE_SQL_TRUST_SERVER_CERTIFICATE", "yes"))

    return URL.create(
        drivername=url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database=url.database,
        query=query,
    )


def _resolve_mssql_target(env: dict[str, str]):
    try:
        from sqlalchemy.engine import URL
    except ModuleNotFoundError as exc:
        raise RuntimeError("SQLAlchemy is required to initialize the database.") from exc

    host = (env.get("ADE_SQL_HOST") or "sql").strip()
    user = (env.get("ADE_SQL_USER") or "sa").strip()
    password = (env.get("ADE_SQL_PASSWORD") or "YourStrong!Passw0rd").strip()
    database = (env.get("ADE_SQL_DATABASE") or "ade").strip()
    encrypt = (env.get("ADE_SQL_ENCRYPT") or "optional").strip()
    trust_cert = (env.get("ADE_SQL_TRUST_SERVER_CERTIFICATE") or "yes").strip()

    auth_mode = (env.get("ADE_DATABASE_AUTH_MODE") or "sql_password").strip().lower()
    if not host or not database:
        raise RuntimeError("Missing required ADE_SQL_* values to initialize the database.")

    try:
        port = int(env.get("ADE_SQL_PORT", "1433"))
    except ValueError as exc:
        raise RuntimeError("ADE_SQL_PORT must be an integer.") from exc

    query = {"driver": "ODBC Driver 18 for SQL Server"}
    if encrypt:
        query["Encrypt"] = encrypt
    if trust_cert:
        query["TrustServerCertificate"] = trust_cert

    if auth_mode == "managed_identity":
        url = URL.create(
            drivername="mssql+pyodbc",
            username=None,
            password=None,
            host=host,
            port=port,
            database="master",
            query=query,
        )
    else:
        url = URL.create(
            drivername="mssql+pyodbc",
            username=user,
            password=password,
            host=host,
            port=port,
            database="master",
            query=query,
        )

    return url, database, auth_mode


def ensure_sql_database(env: dict[str, str]) -> None:
    """Ensure the SQL database exists (creates if missing)."""
    raw_url = (
        env.get("ALEMBIC_DATABASE_URL")
        or env.get("ADE_DATABASE_URL_OVERRIDE")
        or env.get("ADE_DATABASE_URL")
    )
    auth_mode = (env.get("ADE_DATABASE_AUTH_MODE") or "sql_password").strip().lower()

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url
    except ModuleNotFoundError as exc:
        typer.echo(
            "❌ SQLAlchemy is required to initialize the database. "
            "Install ADE dependencies (run `bash scripts/dev/bootstrap.sh`).",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    if raw_url:
        try:
            url = make_url(raw_url)
        except Exception as exc:
            typer.echo(
                f"❌ Failed to parse database URL from env: {exc}",
                err=True,
            )
            raise typer.Exit(code=1) from exc

        backend = url.get_backend_name()
        if backend == "sqlite":
            _ensure_sqlite_parent_dir(raw_url)
            typer.echo("✅ SQLite configured; no SQL Server database to create.")
            return

        if backend != "mssql":
            typer.echo(
                f"⚠️ Unsupported database backend '{backend}' for auto-create; skipping.",
                err=True,
            )
            return

        url = _normalize_mssql_url(url, env)
        if auth_mode == "managed_identity":
            url = url.set(username=None, password=None)
        target_db = (url.database or "").strip()
        if not target_db:
            typer.echo("❌ Database name missing in ADE_DATABASE_URL_OVERRIDE.", err=True)
            raise typer.Exit(code=1)
        if target_db.lower() == "master":
            typer.echo("✅ Database is 'master'; no create step needed.")
            return
        master_url = url.set(database="master")
    else:
        try:
            master_url, target_db, auth_mode = _resolve_mssql_target(env)
        except RuntimeError as exc:
            typer.echo(f"❌ {exc}", err=True)
            raise typer.Exit(code=1) from exc

    engine = create_engine(
        master_url,
        pool_pre_ping=True,
        fast_executemany=True,
        isolation_level="AUTOCOMMIT",
    )

    if auth_mode == "managed_identity":
        try:
            from ade_api.db.azure_sql_auth import attach_azure_sql_managed_identity
        except Exception as exc:
            typer.echo(
                "❌ Managed identity requested but azure-identity is unavailable.",
                err=True,
            )
            raise typer.Exit(code=1) from exc

        client_id = env.get("ADE_DATABASE_MI_CLIENT_ID")
        attach_azure_sql_managed_identity(engine, client_id=client_id)

    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM sys.databases WHERE name = :name"),
                {"name": target_db},
            ).scalar()
            if exists:
                typer.echo(f"✅ SQL database already exists: {target_db}")
                return

            safe_name = target_db.replace("]", "]]")
            typer.echo(f"🗄️  Creating SQL database: {target_db}")
            conn.execute(text(f"CREATE DATABASE [{safe_name}]"))
            typer.echo(f"✅ SQL database created: {target_db}")
    except Exception as exc:
        typer.echo(f"❌ Failed to ensure SQL database '{target_db}': {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        engine.dispose()


def run_init() -> dict[str, str]:
    """Provision SQL database."""
    common.refresh_paths()
    env = common.build_env()
    ensure_sql_database(env)

    return env


def register(app: typer.Typer) -> None:
    @app.command(name="init", help=run_init.__doc__)
    def init() -> None:
        run_init()
