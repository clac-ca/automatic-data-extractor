"""HTTP endpoints for configuration revision resources."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import TypeAdapter
from pydantic.types import StringConstraints
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ConfigurationRevision
from ..schemas import (
    ConfigurationRevisionCreate,
    ConfigurationRevisionResponse,
    ConfigurationRevisionUpdate,
)
from ..services.configuration_revisions import (
    ActiveConfigurationRevisionNotFoundError,
    ConfigurationRevisionNotFoundError,
    create_configuration_revision,
    delete_configuration_revision,
    get_active_configuration_revision,
    get_configuration_revision,
    list_configuration_revisions,
    update_configuration_revision,
)

router = APIRouter(
    prefix="/configuration-revisions", tags=["configuration revisions"]
)

_document_type_adapter = TypeAdapter(
    Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ]
)


def _to_response(
    revision: ConfigurationRevision,
) -> ConfigurationRevisionResponse:
    """Convert ORM objects to response models."""

    return ConfigurationRevisionResponse.model_validate(revision)


@router.post(
    "",
    response_model=ConfigurationRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_configuration_revision_endpoint(
    payload: ConfigurationRevisionCreate,
    db: Session = Depends(get_db),
) -> ConfigurationRevisionResponse:
    """Create a new configuration revision."""

    revision = create_configuration_revision(
        db,
        document_type=payload.document_type,
        title=payload.title,
        payload=payload.payload,
        is_active=payload.is_active,
    )
    return _to_response(revision)


@router.get("", response_model=list[ConfigurationRevisionResponse])
def list_configuration_revisions_endpoint(
    db: Session = Depends(get_db),
) -> list[ConfigurationRevisionResponse]:
    """Return all configuration revisions."""

    revisions = list_configuration_revisions(db)
    return [_to_response(revision) for revision in revisions]


@router.get(
    "/{configuration_revision_id}", response_model=ConfigurationRevisionResponse
)
def get_configuration_revision_endpoint(
    configuration_revision_id: str, db: Session = Depends(get_db)
) -> ConfigurationRevisionResponse:
    """Return a single configuration revision."""

    try:
        revision = get_configuration_revision(db, configuration_revision_id)
    except ConfigurationRevisionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(revision)


@router.get(
    "/active/{document_type}", response_model=ConfigurationRevisionResponse
)
def get_active_configuration_revision_endpoint(
    document_type: str, db: Session = Depends(get_db)
) -> ConfigurationRevisionResponse:
    """Return the active revision for the given configuration."""

    normalized_name = _document_type_adapter.validate_python(document_type)
    try:
        revision = get_active_configuration_revision(db, normalized_name)
    except ActiveConfigurationRevisionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(revision)


@router.patch(
    "/{configuration_revision_id}", response_model=ConfigurationRevisionResponse
)
def update_configuration_revision_endpoint(
    configuration_revision_id: str,
    payload: ConfigurationRevisionUpdate,
    db: Session = Depends(get_db),
) -> ConfigurationRevisionResponse:
    """Update configuration revision metadata."""

    update_kwargs = payload.model_dump(exclude_unset=True)
    try:
        revision = update_configuration_revision(
            db, configuration_revision_id, **update_kwargs
        )
    except ConfigurationRevisionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(revision)


@router.delete(
    "/{configuration_revision_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_configuration_revision_endpoint(
    configuration_revision_id: str, db: Session = Depends(get_db)
) -> Response:
    """Delete a configuration revision."""

    try:
        delete_configuration_revision(db, configuration_revision_id)
    except ConfigurationRevisionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
