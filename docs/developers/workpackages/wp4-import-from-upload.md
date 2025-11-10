# WP4 — Import from Upload (Safe Extract → Unified Create)

## Goal
Let users upload a config archive (zip/tar.gz), scan it safely, and create a draft using the same pipeline introduced in WP1.

## Flow
1. `POST /uploads/config-archive` — multipart upload stored under `${ADE_CONFIGS_DIR}/{workspace}/imports/{upload_id}/`.
2. Safely extract the archive:
   * Support `.zip` and `.tar.gz`.
   * Reject absolute paths, `..`, and symlinks.
   * Enforce archive-level and per-file size limits.
   * Normalize “single top folder vs flat” layouts (choose extracted root automatically).
3. `POST /configurations` with `{ "source": { "type": "upload", "upload_id": "..." } }`.
4. Reuse WP1’s copy → validate → promote flow (no special casing).

## Acceptance
* Malicious archives (traversal, symlinks, oversize files) are rejected gracefully.
* Valid uploads appear under `imports/` and can be promoted exactly once.
* Draft creation via upload produces the same metadata/response shape as template or clone creation.
* Extraction never escapes the workspace imports root.
