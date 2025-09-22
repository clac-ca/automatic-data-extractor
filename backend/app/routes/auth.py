"""Authentication API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import User
from ..schemas import TokenResponse, UserProfile
from ..services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse, openapi_extra={"security": []})
def issue_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    settings: config.Settings = Depends(config.get_settings),
) -> TokenResponse:
    """Exchange email/password credentials for a bearer token."""

    if settings.auth_disabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Authentication is disabled; tokens are unnecessary",
        )

    user = auth_service.authenticate_user(
        db,
        email=form_data.username,
        password=form_data.password,
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = auth_service.create_access_token(user, settings)
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserProfile)
async def who_am_i(current_user: User = Depends(auth_service.get_current_user)) -> UserProfile:
    """Return the profile for the currently authenticated user."""

    return UserProfile.model_validate(current_user)


__all__ = ["router"]
