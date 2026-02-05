# ADE Storage (Azure Blob adapter + layout helpers)

Storage helpers used by ade-api and ade-worker.

## Quickstart

This package is used as a library. Configure via environment variables and
start the services that depend on it.

To validate storage connectivity:

```bash
ade storage check
ade storage reset
```

`ade storage reset` is destructive and requires `--yes`.

## Key commands

```bash
ade storage check
```

## Required env vars (minimal)

- `ADE_BLOB_CONNECTION_STRING` or `ADE_BLOB_ACCOUNT_URL`
- `ADE_BLOB_CONTAINER` (optional; default comes from service settings)
- `ADE_BLOB_PREFIX` (optional)

## Notes

- Azure Blob only (current implementation).
- Blob version handling is controlled by `ADE_BLOB_VERSIONING_MODE` (`auto|require|off`).

## Links

- `../../docs/getting-started/first-run.md`
- `../../docs/reference/cli.md`
