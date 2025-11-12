# DD-0002: Single Active Config per Workspace

Date: 2025-10-29

## Context

Deterministic behavior requires a single source of rules for jobs.

## Decision

Exactly one active config per workspace. Others are `draft` or `archived`.

## Consequences

- Pros: deterministic behavior; simpler UI and APIs.
- Cons: requires activation workflows when switching configs.

## Alternatives considered

- Multiple active configs with selection per job — increases complexity and surprises.

## Links

- See: `../12-glossary.md`
