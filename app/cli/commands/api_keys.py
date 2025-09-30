"""API key management commands for the ADE CLI."""

from __future__ import annotations

from argparse import Namespace
from typing import Any

from app.auth.models import APIKey
from app.auth.service import APIKeyIssueResult, AuthService
from app.core.service import ServiceContext

from ..core.output import ColumnSpec, print_json, print_rows
from ..core.runtime import load_settings, normalise_email, open_session

__all__ = ["issue", "list_keys", "revoke"]


def _serialise_api_key(api_key: APIKey) -> dict[str, Any]:
    user = api_key.user
    return {
        "id": api_key.id,
        "user_id": api_key.user_id,
        "user_email": getattr(user, "email", None),
        "token_prefix": api_key.token_prefix,
        "created_at": api_key.created_at,
        "expires_at": api_key.expires_at,
        "last_seen_at": api_key.last_seen_at,
    }


def _api_key_columns() -> list[ColumnSpec]:
    return [
        ("ID", "id"),
        ("Prefix", "token_prefix"),
        ("User", lambda row: row.get("user_email") or row["user_id"]),
        ("Expires", lambda row: row.get("expires_at") or "-"),
    ]


def _issue_result_payload(result: APIKeyIssueResult) -> dict[str, Any]:
    api_key = _serialise_api_key(result.api_key)
    api_key["principal_type"] = result.principal_type
    api_key["principal_label"] = result.principal_label
    return {"api_key": api_key, "raw_key": result.raw_key}


async def issue(args: Namespace) -> None:
    settings = load_settings()
    async with open_session(settings=settings) as session:
        context = ServiceContext(settings=settings, session=session)
        service = AuthService(context=context)
        expires_in = args.expires_in
        if args.user_id:
            result = await service.issue_api_key_for_user_id(
                user_id=args.user_id,
                expires_in_days=expires_in,
            )
        else:
            email = normalise_email(args.email)
            result = await service.issue_api_key_for_email(
                email=email,
                expires_in_days=expires_in,
            )

    payload = _issue_result_payload(result)
    if args.json:
        print_json(payload)
    else:
        print_rows([payload["api_key"]], _api_key_columns())
        print("Raw key:", payload["raw_key"])


async def list_keys(args: Namespace) -> None:
    settings = load_settings()
    async with open_session(settings=settings) as session:
        context = ServiceContext(settings=settings, session=session)
        service = AuthService(context=context)
        records = await service.list_api_keys()

    serialised = [_serialise_api_key(record) for record in records]
    if args.json:
        print_json({"api_keys": serialised})
    else:
        print_rows(serialised, _api_key_columns())


async def revoke(args: Namespace) -> None:
    settings = load_settings()
    async with open_session(settings=settings) as session:
        context = ServiceContext(settings=settings, session=session)
        service = AuthService(context=context)
        await service.revoke_api_key(args.api_key_id)

    payload = {"revoked": args.api_key_id}
    if args.json:
        print_json(payload)
    else:
        print(f"Revoked API key {args.api_key_id}")
