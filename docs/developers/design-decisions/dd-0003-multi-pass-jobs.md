# DD-0003: Multi‑Pass Jobs

Date: 2025-10-29

## Context

Spreadsheets can be large and messy. Detection benefits from small samples; transformation benefits from column‑wise processing.

## Decision

Four passes: (1) row analysis & headers, (2) detection & mapping (sample‑based), (3) transformation (column‑wise), (4) validation. Optional final hook.

## Consequences

- Pros: memory‑efficient, explainable, controllable pause after mapping.
- Cons: slightly more orchestration between passes.

## Alternatives considered

- Single‑pass processing — mixes concerns, higher memory use, harder to explain.

## Links

- See: `../02-jobs-pipeline.md`
