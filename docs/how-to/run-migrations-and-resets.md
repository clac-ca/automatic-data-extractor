# Run Migrations and Resets

## Goal

Update database schema safely and run destructive resets only when intentional.

## Quick Definitions

- **Migration**: database schema update to match current code.
- **Reset**: destructive operation that removes existing state/data.

## Production Migration Pattern (Azure Container Apps)

1. run migration once from the app container
2. set `ADE_DB_MIGRATE_ON_START=false`
3. deploy or scale only after migration succeeds

## Run Migration Once (Production)

```bash
az containerapp exec \
  --name ade-app \
  --resource-group <resource-group> \
  --command "ade db migrate"
```

Confirm migration revision:

```bash
az containerapp exec \
  --name ade-app \
  --resource-group <resource-group> \
  --command "ade db current"
```

## Local/Repo Migration Commands

```bash
cd backend && uv run ade db migrate
cd backend && uv run ade db current
```

## Baseline Rewrite Note

Auth migration history was rewritten into a deterministic baseline (`0001` + historical placeholders).

If your database is stamped to removed historical revisions (for example `0006_*` from older chains), do not attempt partial upgrade in place for local/dev environments. Reset and reseed instead:

```bash
cd backend && uv run ade db reset --yes
cd backend && uv run ade db migrate
```

## Reset Commands (Destructive)

Combined reset:

```bash
cd backend && uv run ade reset --yes
```

DB-only reset:

```bash
cd backend && uv run ade db reset --yes
```

Storage reset:

```bash
cd backend && uv run ade storage reset --yes --mode prefix
```

## Important Warning

Do not run reset commands in production unless this is part of an approved recovery plan.

## If Something Fails

- stop rollout
- capture migration logs
- restore from backup if needed
- continue with [Triage Playbook](../troubleshooting/triage-playbook.md)
