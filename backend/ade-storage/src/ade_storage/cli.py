"""ade-storage: CLI for ADE storage helpers."""

from __future__ import annotations

import typer
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .factory import build_storage_adapter


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        enable_decoding=False,
        str_strip_whitespace=True,
    )

    blob_account_url: str | None = None
    blob_connection_string: str | None = None
    blob_container: str = "ade"
    blob_prefix: str = "workspaces"
    blob_require_versioning: bool = True
    blob_request_timeout_seconds: float = Field(default=30.0, gt=0)
    blob_max_concurrency: int = Field(default=4, ge=1)
    blob_upload_chunk_size_bytes: int = Field(default=4 * 1024 * 1024, ge=1)
    blob_download_chunk_size_bytes: int = Field(default=1024 * 1024, ge=1)

    @model_validator(mode="after")
    def _finalize(self) -> "StorageSettings":
        if self.blob_connection_string and self.blob_account_url:
            raise ValueError(
                "ADE_BLOB_ACCOUNT_URL must be unset when ADE_BLOB_CONNECTION_STRING is provided."
            )
        if not self.blob_connection_string and not self.blob_account_url:
            raise ValueError("ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL is required.")
        if self.blob_account_url:
            self.blob_account_url = self.blob_account_url.rstrip("/")
        if self.blob_prefix:
            self.blob_prefix = self.blob_prefix.strip("/")
        return self


app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE storage CLI (check connectivity).",
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="check", help="Verify storage connectivity and container access.")
def check() -> None:
    settings = StorageSettings()
    adapter = build_storage_adapter(settings)
    adapter.check_connection()
    typer.echo("✅ storage connection OK")


if __name__ == "__main__":
    app()
