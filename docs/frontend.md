---
Audience: Product managers, frontend engineers, configuration support leads
Goal: Define the ADE frontend blueprint so teams can design and implement the UI with shared guardrails.
Prerequisites: Understanding of ADE configuration concepts and access roles.
When to use: Planning product increments, reviewing UX changes, or onboarding new contributors to the UI.
Validation: Trace key user journeys against the acceptance tests and ensure API contracts remain intact.
Escalate to: ADE product owner for roadmap decisions; frontend lead for implementation questions.
---

# ADE Frontend Blueprint

The ADE interface keeps configuration management approachable by pairing a predictable grid layout with scoped editing rails and server-backed testing. This guide captures the canonical interaction model, lifecycle rules, and operational guardrails so design and engineering changes stay aligned.

## Core domain state

| Object | Lifecycle | Notes |
| --- | --- | --- |
| **Document Type** | Container only | Provides navigation context; no lifecycle states or promotions. |
| **Configuration** | `draft → published → active → retired` | The only versioned entity. Drafts hold live code; publishing snapshots callable source. Use metadata (e.g., `needsApproval`) for reviews instead of extra states. |
| **Column** | `Complete` or `Needs attention` | Flag missing callables, failing tests, or schema issues. No additional lifecycle. |
| **Run** | `queued → running → complete / failed` | Represents execution attempts against an active configuration. |

Only configurations can be promoted, ensuring users focus on version-ready assets instead of sprawling lifecycle states.

## Navigation and layout

- **Persistent scope bar**: `Document Type › Config vN › Run` anchors where the user is working and enables quick jumps back up the hierarchy.
- **Column grid + right rail**: Primary editing surface showing columns as rows with the schema: `Name | Type | Detection | Validation | Transformation | Status`. Selecting a row opens the right rail for editing fields, code, and tests.
- **One primary action per page**: Each screen exposes a single high-impact action (Run, Publish, Promote) to reduce conflicting calls to action.
- **Rails instead of modals**: Use side rails for editing, testing, and confirmation details. Reserve modals solely for final confirmations (e.g., publish, promote).
- **Status chips**: Consistent styling and wording across list, detail, and comparison views so users can correlate states instantly.

## Column callables

- **Single-use per column**: Each column owns its detection, validation, and transformation callables. There is no cross-column reuse or propagation logic.
- **Snapshot on publish**: Publishing freezes callable code inside the configuration version. Drafts remain live for iteration until promoted.
- **Inline editing and testing**: Callables are edited directly within the rail, with immediate lint feedback where applicable.

## Testing workflow

- **Inline test controls**: Every callable panel exposes a **Test** button plus keyboard shortcuts (`⌘↵` for the active callable, `⇧⌘↵` for the full detect → validate → transform pipeline).
- **Sandboxed execution**: Tests always execute via the backend sandbox with deterministic seeds. No client-side evaluation is allowed.
- **Rich results**: Display structured output, logs, error messages, and execution time. Persist the last three runs per callable and allow pinning a “golden” test for regression reference.
- **Run history**: Associate stored test runs with configuration drafts so reconnecting after a disconnect restores recent activity.

## Comparison workflow

1. **Configuration selection**: Default to comparing the latest version, with the option to add up to three configurations total.
2. **Views**:
   - *Side-by-side*: Two or three aligned tables for row-by-row inspection.
   - *Overlay diff*: Single table with per-cell additions, removals, or changes.
   - *Schema diff*: Highlights added, removed, or changed columns and callables.
3. **Default mode**: “Show changes only” to reduce noise, with toggles to reveal unchanged context.
4. **Alignment keys**: Auto-suggest based on unique fields; users can override when needed.
5. **Promotion readiness**: The promotion modal always surfaces schema and code diffs plus metric deltas. Promotion is blocked if validation pass rate drops by more than 5% or required fields are removed.

Comparison is treated as a first-class workflow to validate draft quality before publishing or promoting.

## Runs and guardrails

- **Run lifecycle**: Jobs move from queued to running, then complete or failed. Status chips mirror these phases across dashboards and detail pages.
- **Server-side execution only**: All run validations and callable tests happen on the server to guarantee determinism and auditability.
- **Unsaved draft recovery**: Draft edits cache locally so network hiccups or reloads do not lose work; reconnecting restores the last state.

## API contracts

Lock the following APIs to keep clients and backend aligned:

- **Test callable** — `POST /callables/test`: Payload includes panel type, sample input, and seed. Returns output payload, logs, timings, and error details.
- **Publish configuration** — `POST /configurations/{id}/publish { message }`: Promotes a draft to a published version and returns the new version number.
- **Promote configuration** — `POST /document-types/{id}/promote { version }`: Makes a published configuration active for the document type.
- **Compare configurations** — `GET /configurations/compare`: Responds with schema diffs, metric deltas, alignment suggestions, and cell-level differences.

## Accessibility, performance, and resilience

- Apply ARIA roles to grids, code editors, and live validation feedback.
- Virtualize large tables with sticky headers for orientation on dense documents.
- Execute the diff matrix inside a Web Worker to keep the UI responsive.
- Maintain consistent keyboard navigation and expose shortcut hints within tooltips.

## Analytics to capture

Track usage patterns to iterate on usability and reliability:

- Time to first publish for each configuration.
- Frequency of callable tests compared to run failures.
- Comparison view usage and promotion conversions.
- Draft abandonment rates.
- Median runtime per page segmented by configuration.

## Acceptance tests

- **End-to-end flow**: Home zero state → Document Type → Config with three columns → Test callable → Publish → Promote → Run → Compare, all in 12 steps or fewer.
- **Inline callable test speed**: Results appear with output and status in under one second.
- **Comparison defaults**: Opening comparison shows “changes only” with an auto-suggested alignment key.
- **Promotion guardrail**: Promotion is blocked if validation pass rate regresses by more than five percent.

## Risk trims and guiding principles

- Retire the “under review” state; metadata flags cover approvals without complicating lifecycle logic.
- Keep comparisons capped at three configurations for clarity.
- Favor rails over modal overload to preserve context.
- Reinforce that only configurations are versioned, each column’s callable is independent, and guardrails at publish/promote keep the system safe by default.

These principles keep ADE’s frontend predictable for users and maintainable for engineers while leaving room for iterative improvement.
