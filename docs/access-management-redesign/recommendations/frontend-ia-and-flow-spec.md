# Frontend IA and Flow Spec

## UX Goals

1. Same mental model in org and workspace settings.
2. Minimal clutter: one primary table + one drawer per access surface.
3. Fast path for common tasks: invite/add principal + assign role.
4. Mobile and desktop parity.

## Route Information Architecture

## Organization

- `/organization/access/users`
- `/organization/access/groups`
- `/organization/access/roles`

## Workspace

- `/workspaces/:workspaceId/settings/access/principals`
- `/workspaces/:workspaceId/settings/access/roles`
- `/workspaces/:workspaceId/settings/access/invitations`

Notes:

- “Principals” has segmented tabs: `Users` and `Groups`.
- Keep existing settings shell and side nav design language, but normalize labels and route hierarchy.

## Continuity with Existing Components

Reuse current settings composition patterns:

- `SettingsShell` / `OrganizationSettingsShell`
- `SettingsSection`
- `SettingsDrawer`
- existing table, badge, alert, form components

Do not introduce a new visual system. This is IA and interaction normalization, not a visual rebrand.

## Screen Specs

## 1. Organization Access -> Users

Primary table columns:

1. User
2. Org roles
3. Status
4. Last activity (optional)
5. Actions

Primary action:

- `Invite user` (opens drawer)

Drawer tabs:

- `Profile` (identity fields)
- `Organization roles`
- `Workspace access` (read summary links)

## 2. Organization Access -> Groups

Primary table columns:

1. Group
2. Membership mode (`Assigned` / `Dynamic`)
3. Source (`Internal` / `IdP`)
4. Member count
5. Actions

Primary action:

- `Create group`

Drawer sections:

- Group profile
- Membership management (disabled/read-only if dynamic)
- Role assignments summary

## 3. Workspace Access -> Principals

Tab `Users` and `Groups` share table grammar:

Columns:

1. Principal
2. Workspace roles
3. Source (for groups) or status (for users)
4. Actions

Primary action:

- `Add principal`

Add principal drawer:

1. Choose `User` or `Group`
2. If user:
   - search existing directory
   - or invite by email (same drawer)
3. Assign one or more workspace roles
4. Submit once

## 4. Workspace Access -> Invitations

Primary table columns:

1. Email
2. Workspace
3. Initial roles
4. Status
5. Expires
6. Actions (`Resend`, `Cancel`)

## Interaction Standards

1. Keep one primary CTA per screen.
2. Put destructive actions behind confirmation and visual separation.
3. Preserve deterministic drawer actions:
   - `Cancel`
   - `Save` (or `Invite`) primary on right
   - destructive action separated
4. On mobile, use sticky bottom action bar with clear separation between destructive and primary actions.

## Permission-Aware UI Rules

1. Show what users can view even when they cannot edit.
2. Disable mutation actions with explanatory hint text.
3. Never hide read surfaces if access exists.
4. Workspace owners see invite flow in workspace scope even without org user-admin controls.

## Acceptance Scenarios (UI)

1. Workspace owner can invite unknown email and assign workspace role in one drawer.
2. Workspace owner can add existing user with no duplicate identity creation.
3. Group assignment to workspace reflects effective access for group members.
4. Direct + group role union is visible and understandable.
5. Deactivated user displays as inactive and cannot act.
6. Desktop and mobile flows have equivalent outcomes with no hidden critical action.

