"""User search query tests."""

from __future__ import annotations

from ade_api.common.list_filters import FilterJoinOperator
from ade_api.common.sorting import resolve_sort
from ade_api.core.security.hashing import hash_password
from ade_api.common.ids import generate_uuid7
from ade_api.features.users.service import UsersService
from ade_api.features.users.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_api.models import User

def test_list_users_q_matches_email_and_display_name(session, settings) -> None:
    alpha = User(
        id=generate_uuid7(),
        email="alpha@example.com",
        display_name="Alpha Person",
        hashed_password=hash_password("alpha-password"),
        is_active=True,
    )
    beta = User(
        id=generate_uuid7(),
        email="beta@example.com",
        display_name="Beta Person",
        hashed_password=hash_password("beta-password"),
        is_active=True,
    )
    session.add_all([alpha, beta])
    session.flush()

    service = UsersService(session=session, settings=settings)
    order_by = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )

    result = service.list_users(
        page=1,
        per_page=50,
        order_by=order_by,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q="alpha",
    )

    emails = [user.email for user in result.items]
    assert "alpha@example.com" in emails
    assert "beta@example.com" not in emails
