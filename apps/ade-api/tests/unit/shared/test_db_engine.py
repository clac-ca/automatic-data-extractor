import struct
from types import SimpleNamespace

import pytest

from ade_api.db import engine as db_engine
from ade_api.db.engine import (
    _AZURE_SQL_SCOPE,
    _SQL_COPT_SS_ACCESS_TOKEN,
    _managed_identity_injector,
    build_database_url,
)
from ade_api.settings import Settings


def test_build_database_url_removes_sql_credentials_for_managed_identity() -> None:
    settings = Settings(
        database_dsn=(
            "mssql+pyodbc://user:secret@contoso.database.windows.net:1433/ade"
            "?Trusted_Connection=yes"
        ),
        database_auth_mode="managed_identity",
    )

    url = build_database_url(settings)

    assert url.username is None
    assert url.password is None
    assert "Trusted_Connection" not in url.query


def test_managed_identity_injector_sets_access_token_and_strips_auth() -> None:
    token_bytes = "token-value".encode("utf-16-le")
    injector = _managed_identity_injector(lambda: struct.pack("<I", len(token_bytes)) + token_bytes)
    cparams = {
        "user": "alice",
        "password": "secret",
        "attrs_before": {"foo": "bar"},
        "Authentication": "ActiveDirectoryMsi",
    }

    injector(None, None, None, cparams)

    expected_token = struct.pack("<I", len(token_bytes)) + token_bytes
    assert cparams["attrs_before"][_SQL_COPT_SS_ACCESS_TOKEN] == expected_token
    assert "user" not in cparams
    assert "password" not in cparams
    assert "Authentication" not in cparams


def test_managed_identity_token_provider_returns_utf16le_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str | None] = {}

    def _fake_default_credential(*, managed_identity_client_id=None):
        captured["client_id"] = managed_identity_client_id

        class _Cred:
            def get_token(self, scope: str) -> SimpleNamespace:
                captured["scope"] = scope
                return SimpleNamespace(token="abc")

        return _Cred()

    monkeypatch.setattr(db_engine, "DefaultAzureCredential", _fake_default_credential)

    settings = Settings(
        database_dsn=(
            "mssql+pyodbc://contoso.database.windows.net:1433/ade"
            "?driver=ODBC+Driver+18+for+SQL+Server"
        ),
        database_auth_mode="managed_identity",
    )

    provider = db_engine._managed_identity_token_provider(settings)
    token = provider()

    expected_body = "abc".encode("utf-16-le")
    assert token == struct.pack("<I", len(expected_body)) + expected_body
    assert captured == {
        "client_id": None,
        "scope": _AZURE_SQL_SCOPE,
    }
