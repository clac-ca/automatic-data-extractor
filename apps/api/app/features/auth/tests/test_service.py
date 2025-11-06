from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import Request

from apps.api.app.features.auth.service import AuthService
from apps.api.app.shared.core.config import Settings


def _make_request(*, scheme: str = "http", headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in (headers or {}).items()]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "scheme": scheme,
        "server": ("testserver", 443 if scheme == "https" else 80),
    }
    return Request(scope)


def test_is_secure_request_trusts_forwarded_proto_only_for_https() -> None:
    service = AuthService(session=MagicMock(), settings=Settings())

    request = _make_request(headers={"X-Forwarded-Proto": "https"})

    assert service.is_secure_request(request) is True


def test_is_secure_request_ignores_forwarded_proto_http_downgrade() -> None:
    service = AuthService(session=MagicMock(), settings=Settings())

    request = _make_request(scheme="https", headers={"X-Forwarded-Proto": "http"})

    assert service.is_secure_request(request) is True


def test_is_secure_request_uses_scope_scheme_when_available() -> None:
    service = AuthService(session=MagicMock(), settings=Settings())

    request = _make_request(scheme="https")

    assert service.is_secure_request(request) is True
