"""CLI entry point for purging expired documents."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import asdict
from typing import Sequence

from ..db import Base, get_engine, get_sessionmaker
from ..services.documents import (
    ExpiredDocumentPurgeSummary,
    PurgedDocument,
    purge_expired_documents,
)

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove expired documents and update metadata to reflect the purge.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of documents to purge during this run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be purged without deleting any data.",
    )
    return parser


def _validate_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    limit = args.limit
    if limit is not None and limit <= 0:
        parser.error("--limit must be greater than zero")


def _ensure_schema() -> None:
    # Import models so SQLAlchemy knows about the tables before create_all.
    from .. import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def _format_document(detail: PurgedDocument) -> str:
    status = "missing" if detail.missing_before_delete else "purged"
    return (
        f"{detail.document_id} | expires {detail.expires_at} | "
        f"{detail.byte_size:,} bytes | {status}"
    )


def _print_summary(summary: ExpiredDocumentPurgeSummary) -> None:
    header = "Dry run" if summary.dry_run else "Purge"
    print(f"{header} complete.")
    print(f"Processed: {summary.processed_count}")
    print(f"Missing files: {summary.missing_files}")
    print(f"Bytes reclaimed: {summary.bytes_reclaimed:,}")

    if not summary.documents:
        print("No expired documents matched the criteria.")
        return

    print("\nDocuments:")
    for detail in summary.documents:
        print(f"  - {_format_document(detail)}")


def _log_summary(summary: ExpiredDocumentPurgeSummary) -> None:
    summary_dict = asdict(summary)
    logger.info("Expired document purge finished", extra={"summary": summary_dict})


def _run_purge(limit: int | None, dry_run: bool) -> ExpiredDocumentPurgeSummary:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        return purge_expired_documents(db, limit=limit, dry_run=dry_run)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_arguments(parser, args)
        _ensure_schema()
        summary = _run_purge(args.limit, args.dry_run)
        _log_summary(summary)
        _print_summary(summary)
        return 0
    except SystemExit:
        raise
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Expired document purge failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
