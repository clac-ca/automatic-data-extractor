from app.features.auth import service as auth_service
from app.features.auth.schemas import LoginRequest


def test_login_success() -> None:
    resp = auth_service.login(LoginRequest(username="demo", password="demo"))
    assert resp.ok is True
    assert resp.token == "demo-token"


def test_login_failure() -> None:
    resp = auth_service.login(LoginRequest(username="demo", password="wrong"))
    assert resp.ok is False
