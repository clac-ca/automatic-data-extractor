# UI Playwright Audit (Organization Users + Workspace Members)

Date: February 11, 2026

## Test Setup

- App host: `http://localhost:30331`
- API health: `http://localhost:31331/health` (healthy during run)
- Browser automation: Playwright CLI
- Evidence artifacts: `.playwright-cli/page-2026-02-11T23-*.yml` and `.playwright-cli/page-2026-02-11T23-*.png`
- Additional screenshots supplied by user (desktop + mobile states)

## Flows Executed

1. Organization settings -> Users list -> Create user drawer -> Manage user drawer.
2. Workspace settings -> Access/Members list -> Add member drawer -> Manage member drawer.
3. Mobile checks for org users and workspace member management drawers.

## Findings (Subtle UI/UX Flaws)

### P0: Creation flow gap (permission model mismatch)

- In org “Create user”, there is no role/permission assignment section.
- In workspace “Add member”, role assignment is required at creation.
- Net effect: users are created globally first, then permissions are configured separately, which breaks flow continuity and causes avoidable post-create steps.
- This is the key blocker you called out.

### P1: Identity context degrades to opaque IDs

- Workspace members list and member drawer can render UUIDs instead of name/email.
- Example fallback paths are visible in UI code and in screenshots.
- This makes access decisions error-prone in real teams.

### P1: Organization and workspace access surfaces are conceptually similar but visually/structurally split

- Org uses “Users” semantics and global profile controls.
- Workspace uses “Members” semantics and assignment-only controls.
- Layouts are close but not truly unified: different terms, different row data density, different drawer mental model.

### P1: Route and IA inconsistency leaks into UX

- Org path family is `/organization/users|roles|...`.
- Workspace path family is `/workspaces/:id/settings/access/...`.
- Similar concepts live under unrelated route structures; this hurts predictability and deep-linking consistency.

### P1: Add-member flow is hiddenly dependent on global directory access

- “Add member” starts with directory search/select rather than explicit invite-or-existing branching.
- If directory visibility is restricted, workspace-owner flow can fail without clear guidance.

### P2: Action hierarchy in drawers is not consistently safe

- In manage-member drawer, destructive “Remove” sits adjacent to “Save changes,” especially tight on mobile.
- Primary/secondary/destructive intent separation should be clearer.

### P2: Mobile drawer ergonomics are serviceable but not first-class

- Dense action row in footer, long IDs, and limited visual grouping increase scan cost.
- Important context (who this user is, where this access applies) is not compressed effectively for small screens.

### P2: Status and role chips are inconsistent across org/workspace tables

- Org table includes status + roles in one row pattern.
- Workspace table emphasizes roles but lacks equivalent status cues (active/inactive/invited).
- Users cannot quickly compare access posture across scopes.

### P3: Terminology drift increases cognitive load

- “Create user,” “Add member,” “Manage,” “Users,” and “Members” are semantically close but not aligned.
- The product needs a single “principal + assignment” language model while preserving org/workspace intent.

## Evidence Mapped to Artifacts

- Organization users surfaces: `.playwright-cli/page-2026-02-11T23-36-27-341Z.yml`, `.playwright-cli/page-2026-02-11T23-36-43-134Z.png`
- Workspace members surfaces: `.playwright-cli/page-2026-02-11T23-37-46-739Z.yml`, `.playwright-cli/page-2026-02-11T23-37-50-734Z.png`, `.playwright-cli/page-2026-02-11T23-38-04-101Z.png`
- Mobile checks: `.playwright-cli/page-2026-02-11T23-39-24-885Z.yml`, `.playwright-cli/page-2026-02-11T23-39-28-310Z.png`, `.playwright-cli/page-2026-02-11T23-40-10-004Z.png`

## UI Design Principles Derived from Audit

1. Keep one canonical model on screen: `Principal -> Assignments -> Effective access`.
2. Make creation contextual: create/invite and assign access in one flow.
3. Use the same table/drawer grammar in org and workspace surfaces.
4. Keep role edits lightweight, but isolate destructive actions.
5. Preserve compactness: no extra panels unless they directly reduce user errors.

