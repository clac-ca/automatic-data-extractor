# Unified Settings QA Checklist

## Route and navigation

- [ ] `/settings` renders and shows only authorized top-level entry surfaces.
- [ ] Rail contains grouped sections (`Home`, `Organization`, `Workspaces`).
- [ ] Unauthorized sections are absent from rail and blocked by direct URL.
- [ ] Workspace sidebar `Settings` link opens `/settings/workspaces/:workspaceId/general`.
- [ ] Profile menu `Settings` link opens `/settings`.

## Organization flows

- [ ] Users list row click navigates to `/settings/organization/users/:userId`.
- [ ] Users create route `/settings/organization/users/create` opens create surface.
- [ ] Groups list row click navigates to `/settings/organization/groups/:groupId`.
- [ ] Groups create route `/settings/organization/groups/create` opens create surface.
- [ ] Roles list row click navigates to `/settings/organization/roles/:roleId`.
- [ ] Roles create route `/settings/organization/roles/create` opens create surface.

## Workspace flows

- [ ] Workspace list route `/settings/workspaces` opens list-first view.
- [ ] Section switch keeps selected workspace and updates URL.
- [ ] Principals detail deep link resolves and edits expected principal.
- [ ] Roles detail deep link resolves and edits expected role.
- [ ] Invitations detail deep link resolves expected invitation.
- [ ] Invitations create route `/settings/workspaces/:workspaceId/access/invitations/new` creates invitation.

## UX and behavior

- [ ] Entity detail experiences are full-page (no narrow right-side pane).
- [ ] Save/discard controls are discoverable for dirty forms.
- [ ] Unsaved changes protection appears where expected.
- [ ] Loading/empty/error states render consistently.
- [ ] List views preserve `q`, `sort`, `order`, `page`, `pageSize`, and section filters in URL query parameters.
- [ ] Keyboard row activation works via `Enter` and `Space` on list rows.
- [ ] Failed create/update submissions show error summary + field-level errors with field anchors.
- [ ] Workspace switch preserves section when authorized and falls back to `/general` when not authorized.

## Legacy behavior

- [ ] `/organization/*` is no longer route-registered.
- [ ] `/workspaces/:workspaceId/settings/*` no longer resolves a settings section.
- [ ] `/account/*` behavior remains unchanged.
- [ ] SSO setup popup flow still works in Authentication.
