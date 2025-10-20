from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


auth_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> str:
    """
    Placeholder dependency for authenticated routes.
    Replace with JWT/session validation when auth is implemented.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    # In a real implementation validate token and return user/sub claim.
    return credentials.credentials
