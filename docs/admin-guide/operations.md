# Operational Tasks with the ADE CLI

The `ade` command ships with the backend package and provides a small surface
for day-to-day administration. Commands mirror the FastAPI modules so that
operators can reuse the same terminology across HTTP and CLI workflows. Tables
are printed by default; pass `--json` to receive machine-readable output.

## Bootstrapping an administrator

When a new environment is provisioned you typically create the first human
administrator manually. Run the following command after installing the backend
with `pip install -e .[dev]` or deploying the packaged wheel:

```bash
ade users create --email admin@example.com --password "S3cureP@ss" --role admin
```

Important notes:

- The email is normalised (trimmed and lowercased) before storage to avoid
  duplicates.
- `--password` may be replaced with `--password-file /path/to/secret.txt` to
  read credentials from disk.
- Use `--inactive` if you want to stage an account that will be activated later
  by another administrator.

## Resetting a password

Passwords can be rotated without touching the database directly. Provide either
`--password` or `--password-file`, and locate the account via its identifier or
email address:

```bash
ade users set-password --email admin@example.com --password-file ~/.secrets/new-password.txt
```

The command updates the stored hash and returns the user's active state so you
can confirm the account is enabled.

Activation and deactivation behave the same way. Either supply the database ID
as a positional argument or add `--email user@example.com` when the ID is not
readily available.

## Issuing or revoking API keys

Service integrations authenticate via API keys. Each key is tied to a user and
can be limited to a specific lifetime.

```bash
# Issue a key valid for 30 days
ade api-keys issue --user-id 01J123ABC456DEF789GH --expires-in 30 --json
```

The response includes the raw secret exactly once. Store it securely; only the
hashed prefix is retained in the database. To inspect existing keys run:

```bash
ade api-keys list
```

and revoke a key when it is no longer needed:

```bash
ade api-keys revoke 01KZYXWVUTSRQPONML
```

The audit fields (`created_at`, `last_seen_at`) are returned in JSON output,
which is helpful when scripting expiry reports or alerts.
