# Unified `/settings` UX Blueprint

## IA

- `Settings`
  - `Home`
  - `Organization`
    - `Users`
    - `Groups`
    - `Roles`
    - `API keys`
    - `Authentication`
    - `Run controls`
  - `Workspaces`
    - `All workspaces`
    - `General`
    - `Processing`
    - `Access > Principals`
    - `Access > Roles`
    - `Access > Invitations`
    - `Lifecycle > Danger`

Unauthorized sections are hidden from the rail and blocked on direct URL access.

## Route map

### Home
- `/settings`

### Organization
- `/settings/organization/users`
- `/settings/organization/users/new`
- `/settings/organization/users/:userId`
- `/settings/organization/groups`
- `/settings/organization/groups/new`
- `/settings/organization/groups/:groupId`
- `/settings/organization/roles`
- `/settings/organization/roles/new`
- `/settings/organization/roles/:roleId`
- `/settings/organization/api/keys`
- `/settings/organization/authentication`
- `/settings/organization/run/controls`

### Workspaces
- `/settings/workspaces`
- `/settings/workspaces/:workspaceId/general`
- `/settings/workspaces/:workspaceId/processing`
- `/settings/workspaces/:workspaceId/access/principals`
- `/settings/workspaces/:workspaceId/access/principals/new`
- `/settings/workspaces/:workspaceId/access/principals/:principalType/:principalId`
- `/settings/workspaces/:workspaceId/access/roles`
- `/settings/workspaces/:workspaceId/access/roles/new`
- `/settings/workspaces/:workspaceId/access/roles/:roleId`
- `/settings/workspaces/:workspaceId/access/invitations`
- `/settings/workspaces/:workspaceId/access/invitations/new`
- `/settings/workspaces/:workspaceId/access/invitations/:invitationId`
- `/settings/workspaces/:workspaceId/lifecycle/danger`

### Legacy policy
- `/organization/*`: removed from route registration.
- `/workspaces/:workspaceId/settings/*`: no longer a valid workspace section resolver path.

## Page templates

### List page template

- Header block: title + concise subtitle.
- Command bar: search, filters, primary action.
- Primary table: full-width list with row action menu.
- Row click: navigates to full-page detail route.

### Detail page template

- Full-page detail surface (no narrow right pane).
- Strong header with back affordance.
- Content sections grouped by task.
- Sticky action area for save/discard when dirty.
- Confirm dialogs for destructive actions.

## Interaction rules

1. Route is the source of truth for selection state.
2. `/create` routes open creation surfaces.
3. Entity IDs in URL are canonical and shareable.
4. Workspace rail section links preserve selected workspace context.
5. Workspace sidebar `Settings` entry opens `/settings/workspaces/:workspaceId/general`.
6. Workspace switching preserves the current subsection when authorized, and falls back to `general` when unauthorized.

## List-state query contract

Settings list pages use a consistent URL query model:

- `q`: text search
- `sort`: field key
- `order`: `asc` or `desc`
- `page`: 1-based page index
- `pageSize`: rows per page
- page-specific filters (for example `status`, `principalType`)

This enables deep-linking list views and preserving list context when moving between list and detail routes.

## Micro-interaction rules (v2)

1. Row activation is consistent: click row or press `Enter`/`Space` to open details.
2. Open action in the rightmost cell is a fallback, not the primary interaction.
3. Form submit failures show both field-level errors and a top error summary with field anchors.
4. Page feedback follows one region model with consistent success/error placement and `aria-live`.
5. Sticky action bars show save disabled reasons where relevant.
6. Detail page headings receive focus on route transitions for keyboard users.

## Visual and spacing rules

1. One dominant content region per screen.
2. Avoid fragmented micro-cards for core settings tasks.
3. Keep list and detail layouts dense but readable.
4. Reuse ADE typography/tokens/components (no Fluent UI imports).

## Accessibility and responsive requirements

1. Semantic headings and landmark ordering preserved per page.
2. Keyboard focus does not trap in list/detail transitions.
3. Mobile retains action access and filter controls without clipping.
4. Destructive actions always require explicit confirmation.
