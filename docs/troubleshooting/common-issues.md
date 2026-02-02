# Common issues

## View logs

```bash
docker compose logs -f
```

## Web UI shows a blank page

- Ensure the frontend build exists (`ade web build`).
- If using nginx, confirm it serves `/usr/share/nginx/html`.

## Versions endpoint shows web version as "unknown"

- Ensure `version.json` exists in the web build output.
- Override the path with `ADE_WEB_VERSION_FILE` if needed.

## Database connection errors

- Verify `ADE_DATABASE_URL` is correct and reachable.
- Ensure SSL settings match the database (`sslmode`, `ADE_DATABASE_SSLROOTCERT`).

## Blob storage errors

- Confirm `ADE_BLOB_CONNECTION_STRING` or `ADE_BLOB_ACCOUNT_URL` is set.
- Ensure the container exists and the credentials have read/write access.

## Migrations fail

- Re-run `ade db migrate`.
- Check that the DB user has schema migration permissions.
