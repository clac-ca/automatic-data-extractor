# Access UI Competitive Patterns Matrix (Entra + Peers)

Date: February 12, 2026

## Purpose

Compare access-management UI patterns by task quality, not brand preference, to
select the best target model for ADE.

## Scoring Model

Scale: `1` (weak) to `5` (strong).

Criteria:

1. Task clarity (admins can predict where to act).
2. Click depth (few context switches to complete task).
3. Permission boundary explainability (role/scope requirements are understandable).
4. Provider-managed handling (read-only constraints + clear guidance).
5. Bulk readiness (discoverable and safe high-volume operations).

## Product Pattern Scores

| Product | Task clarity | Click depth | Boundary explainability | Provider-managed handling | Bulk readiness | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Microsoft Entra | 5 | 4 | 5 | 5 | 5 | Strong assignment and group admin patterns; best enterprise baseline. |
| Okta | 4 | 4 | 5 | 4 | 3 | Strong delegated admin model; bulk UX less unified than Entra. |
| Google Workspace Admin | 4 | 4 | 4 | 4 | 3 | Good user->groups workflows and API support; mixed admin-console consistency. |
| GitHub Enterprise | 4 | 5 | 4 | 5 | 3 | Excellent invite/team flow; team sync read-only model is explicit. |
| Atlassian Admin | 4 | 3 | 5 | 4 | 3 | Clear admin-role model; some tasks involve more context switches. |

## Task-by-Task Pattern Comparison

| Task | Entra | Okta | Google | GitHub | Atlassian | ADE target |
| --- | --- | --- | --- | --- | --- | --- |
| Create user with assignments | Guided flow with assignment surfaces | Create with optional groups | User and group admin actions in account/group surfaces | Invite with role and optional team | Grant access via groups/roles | Multi-step create with assignment tab + optional workspace seed |
| Group membership from group page | Members + Owners management in group detail | Manual assign/remove members | Group page member management | Team members management | Group edit supports members | Group detail must support add/remove members and owners |
| Group membership from user page | Membership views and assignment patterns supported in ecosystem | Mostly group-centric | Explicit add user to groups from user account | Team/org role from membership surfaces | Mixed; group-centric common | User detail must include group membership editor |
| Provider-managed constraints | Dynamic/role constraints explicit | Group push constraints explicit | Dynamic groups are query-managed | Team sync memberships managed in IdP | SCIM-provisioned constraints | Show read-only state with why + next step |
| Bulk operations | Explicit bulk entry points and docs | Admin actions available, less standardized UI | API-heavy for scale operations | Some bulk via automation/APIs | Admin operations, mixed surface | Command-bar bulk actions with partial-success panel |

## Chosen Pattern Set for ADE

1. Adopt Entra-style task grouping and assignment ergonomics as primary model.
2. Adopt Okta/Atlassian delegated-admin clarity for permission boundaries.
3. Adopt GitHub team-sync style read-only enforcement language for IdP-managed groups.
4. Adopt Google user-account group-edit parity pattern so group membership is manageable
   from both group and user views.

## Inferences (Explicit)

1. Inference: no single vendor is ideal across all tasks; combining Entra structure
   with Google user-centric membership patterns yields the best operator UX for ADE.
2. Inference: the fastest usability lift comes from improving editability and
   affordance clarity, not adding more pages.

## Source References

See:

1. `docs/access-management-redesign/research/access-ui-task-flows-entra-plus-peers.md`
2. `docs/access-management-redesign/research/entra-admin-ui-patterns.md`
