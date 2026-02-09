# DD-0001: File-backed Configs

Date: 2025-10-29

## Context

Configs are authored and reviewed as code. We need portability and transparency.

## Decision

One folder per config; export/import by zipping the folder. Database stores metadata and index only.

## Consequences

- Pros: diffable, reviewable, portable; simple backup/restore.
- Cons: must handle filesystem consistency and indexing.

## Alternatives considered

- DB-stored configs (blobs) — harder to review/port.

## Links

- See: `../01-config-packages.md`
