"""Tests that focus on configuration revision race conditions."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.db import get_sessionmaker
from backend.app.models import Configuration
from backend.app.services import configurations as configurations_service


def test_concurrent_activation_allows_only_one_active_revision(
    app_client, monkeypatch
) -> None:
    """Simulate concurrent activations and ensure only one succeeds."""

    _ = app_client
    session_factory = get_sessionmaker()

    with session_factory() as session:
        configurations_service.create_configuration(
            session,
            document_type="invoice",
            title="Base active",
            payload={"rows": []},
            is_active=True,
        )
        candidate_a = configurations_service.create_configuration(
            session,
            document_type="invoice",
            title="Candidate A",
            payload={"rows": []},
        )
        candidate_b = configurations_service.create_configuration(
            session,
            document_type="invoice",
            title="Candidate B",
            payload={"rows": []},
        )

    barrier = threading.Barrier(2)
    gate = threading.Event()
    original_demote = getattr(
        configurations_service, "_demote_other_active_configurations"
    )

    def _awaiting_demote(
        db_session, *, document_type: str, configuration_id: str
    ) -> None:
        if gate.is_set():
            barrier.wait()
        original_demote(
            db_session,
            document_type=document_type,
            configuration_id=configuration_id,
        )

    monkeypatch.setattr(
        configurations_service,
        "_demote_other_active_configurations",
        _awaiting_demote,
    )

    def _activate(configuration_id: str) -> str:
        with session_factory() as session:
            try:
                configurations_service.update_configuration(
                    session,
                    configuration_id,
                    is_active=True,
                )
            except IntegrityError:
                return "integrity_error"
            return "activated"

    gate.set()
    results: list[str] = []
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(_activate, candidate_a.configuration_id),
                executor.submit(_activate, candidate_b.configuration_id),
            ]
            results = [future.result() for future in futures]
    finally:
        gate.clear()

    assert results.count("activated") == 1
    assert results.count("integrity_error") == 1

    with session_factory() as session:
        active_configurations = session.scalars(
            select(Configuration).where(
                Configuration.document_type == "invoice",
                Configuration.is_active.is_(True),
            )
        ).all()

        assert len(active_configurations) == 1
        winning_id = active_configurations[0].configuration_id
        assert winning_id in {
            candidate_a.configuration_id,
            candidate_b.configuration_id,
        }

        losing_id = (
            candidate_b.configuration_id
            if winning_id == candidate_a.configuration_id
            else candidate_a.configuration_id
        )
        losing_configuration = session.get(Configuration, losing_id)
        assert losing_configuration is not None
        assert losing_configuration.is_active is False
        assert losing_configuration.activated_at is None
