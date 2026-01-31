"""Unit tests for auth pipeline ordering."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from ade_api.core.auth.pipeline import authenticate_websocket
from ade_api.core.auth.principal import AuthVia, AuthenticatedPrincipal, PrincipalType
from ade_api.settings import Settings


class StubAuthenticator:
    def __init__(self, result: AuthenticatedPrincipal | None) -> None:
        self.result = result
        self.calls: list[str] = []

    def authenticate(self, token: str) -> AuthenticatedPrincipal | None:
        self.calls.append(token)
        return self.result


class FakeWebSocket:
    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
    ) -> None:
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.query_params = query_params or {}


class FakeSession:
    def __init__(self, users: dict[UUID, object]) -> None:
        self._users = users

    def get(self, _model: object, user_id: UUID) -> object | None:
        return self._users.get(user_id)


def _principal(user_id: UUID, auth_via: AuthVia) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id,
        principal_type=PrincipalType.USER,
        auth_via=auth_via,
    )


def _user(user_id: UUID) -> object:
    return SimpleNamespace(id=user_id, is_active=True)


def test_authenticate_websocket_prefers_api_key() -> None:
    api_user_id = uuid4()
    bearer_user_id = uuid4()
    cookie_user_id = uuid4()

    api_service = StubAuthenticator(_principal(api_user_id, AuthVia.API_KEY))
    bearer_service = StubAuthenticator(_principal(bearer_user_id, AuthVia.BEARER))
    cookie_service = StubAuthenticator(_principal(cookie_user_id, AuthVia.SESSION))

    websocket = FakeWebSocket(
        headers={
            "authorization": "Bearer bearer-token",
            "x-api-key": "prefix.secret",
        },
        cookies={"ade_session": "cookie-token"},
    )
    settings = Settings(
        _env_file=None,
        secret_key="test-secret-key-for-tests-please-change",
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
    )
    session = FakeSession(
        {
            api_user_id: _user(api_user_id),
            bearer_user_id: _user(bearer_user_id),
            cookie_user_id: _user(cookie_user_id),
        }
    )

    principal = authenticate_websocket(
        websocket,
        session,
        settings,
        api_service,
        cookie_service,
        bearer_service,
    )

    assert principal.user_id == api_user_id
    assert principal.auth_via is AuthVia.API_KEY
    assert bearer_service.calls == []
    assert cookie_service.calls == []


def test_authenticate_websocket_prefers_bearer_over_cookie() -> None:
    bearer_user_id = uuid4()
    cookie_user_id = uuid4()

    api_service = StubAuthenticator(None)
    bearer_service = StubAuthenticator(_principal(bearer_user_id, AuthVia.BEARER))
    cookie_service = StubAuthenticator(_principal(cookie_user_id, AuthVia.SESSION))

    websocket = FakeWebSocket(
        headers={"authorization": "Bearer bearer-token"},
        cookies={"ade_session": "cookie-token"},
    )
    settings = Settings(
        _env_file=None,
        secret_key="test-secret-key-for-tests-please-change",
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
    )
    session = FakeSession(
        {
            bearer_user_id: _user(bearer_user_id),
            cookie_user_id: _user(cookie_user_id),
        }
    )

    principal = authenticate_websocket(
        websocket,
        session,
        settings,
        api_service,
        cookie_service,
        bearer_service,
    )

    assert principal.user_id == bearer_user_id
    assert principal.auth_via is AuthVia.BEARER
    assert cookie_service.calls == []


def test_authenticate_websocket_prefers_cookie_over_query_param() -> None:
    cookie_user_id = uuid4()
    query_user_id = uuid4()

    api_service = StubAuthenticator(None)
    bearer_service = StubAuthenticator(None)
    cookie_service = StubAuthenticator(_principal(cookie_user_id, AuthVia.SESSION))

    websocket = FakeWebSocket(
        cookies={"ade_session": "cookie-token"},
        query_params={"access_token": "query-token"},
    )
    settings = Settings(
        _env_file=None,
        secret_key="test-secret-key-for-tests-please-change",
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
    )
    session = FakeSession(
        {
            cookie_user_id: _user(cookie_user_id),
            query_user_id: _user(query_user_id),
        }
    )

    principal = authenticate_websocket(
        websocket,
        session,
        settings,
        api_service,
        cookie_service,
        bearer_service,
    )

    assert principal.user_id == cookie_user_id
    assert principal.auth_via is AuthVia.SESSION
    assert bearer_service.calls == []


def test_authenticate_websocket_falls_back_to_query_param() -> None:
    query_user_id = uuid4()

    api_service = StubAuthenticator(None)
    bearer_service = StubAuthenticator(_principal(query_user_id, AuthVia.BEARER))
    cookie_service = StubAuthenticator(None)

    websocket = FakeWebSocket(query_params={"access_token": "query-token"})
    settings = Settings(
        _env_file=None,
        secret_key="test-secret-key-for-tests-please-change",
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
    )
    session = FakeSession({query_user_id: _user(query_user_id)})

    principal = authenticate_websocket(
        websocket,
        session,
        settings,
        api_service,
        cookie_service,
        bearer_service,
    )

    assert principal.user_id == query_user_id
    assert principal.auth_via is AuthVia.BEARER
