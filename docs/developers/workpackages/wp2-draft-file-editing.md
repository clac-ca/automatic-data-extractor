# WP2 — Draft File Editing API

## Goal
Expose safe CRUD endpoints so editors can modify draft config files in place while protecting active/inactive configs from mutation.

## Scope
Implement endpoints under `/api/v1/workspaces/{workspace}/configurations/{config}`:

1. `GET /files` — list the tree (path, type, size, mtime).
2. `GET /files/content?path=` — fetch file bytes/text with `content`, `encoding`, and `etag`.
3. `PUT /files/content` — create or update file content (requires `if_match` ETag on updates).
4. `POST /files/move` — rename/move files (support `overwrite` flag).
5. `DELETE /files` — delete a file/directory (with optional `recursive`).

## Rules
* Only `status='draft'` configs are editable; others return `409 config_not_editable`.
* Normalize relative paths, reject traversal, and refuse to operate on symlinks.
* Generate strong ETags per file (e.g., SHA-256 of content + mtime + size); `if_match` is mandatory for overwrites.
* Enforce size limits inside `src/ade_config/**`; allow larger assets under `assets/` or similar whitelisted folders.

## Acceptance
* All CRUD operations succeed for drafts and are blocked for active/inactive configs.
* ETag conflicts are detected and surfaced to clients.
* Listing and reads work across all statuses for inspection purposes.
* Attempts at path traversal, symlink usage, or other unsafe operations are rejected with clear errors.
