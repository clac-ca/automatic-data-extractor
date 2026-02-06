# Manage Users and Access

## Goal

Create users, update user status, and assign roles from the CLI.

## Quick Definitions

- **User**: person or service account that can access ADE.
- **Role**: named permission bundle.
- **Scope**:
  - `global`: applies everywhere.
  - `workspace`: applies only in one workspace.

## List and Create Users

List users:

```bash
cd backend && uv run ade-api users list
```

Create admin user:

```bash
cd backend && uv run ade-api users create-admin admin@example.com --display-name 'ADE Admin'
```

Create regular user:

```bash
cd backend && uv run ade-api users create user@example.com --display-name 'User One'
```

## Activate or Deactivate

```bash
cd backend && uv run ade-api users deactivate user@example.com
cd backend && uv run ade-api users activate user@example.com
```

## Assign Roles

Global role:

```bash
cd backend && uv run ade-api users roles assign user@example.com global-admin --scope global
```

Workspace role:

```bash
cd backend && uv run ade-api users roles assign user@example.com workspace-editor --scope workspace --workspace-id <workspace-uuid>
```

Remove role:

```bash
cd backend && uv run ade-api users roles remove --user user@example.com --role workspace-editor --scope workspace --workspace-id <workspace-uuid>
```

## Verify

```bash
cd backend && uv run ade-api users show user@example.com
cd backend && uv run ade-api users roles list user@example.com
```

## If Something Fails

- If you lock yourself out, use another admin account.
- Check auth settings in [Security and Authentication](../explanation/security-and-authentication.md).
