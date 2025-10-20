from .schemas import LoginRequest, LoginResponse

# Hard-coded credentials strictly for bootstrapping the project layout.
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo"


def login(payload: LoginRequest) -> LoginResponse:
    if payload.username == DEMO_USERNAME and payload.password == DEMO_PASSWORD:
        return LoginResponse(ok=True, token="demo-token")
    return LoginResponse(ok=False, message="Invalid credentials")


def logout() -> LoginResponse:
    return LoginResponse(ok=True, message="Signed out")
