# Current Task — Document expiration defaults

## Goal
Attach an expiration timestamp to uploaded documents so operators have a
simple policy to follow while we line up cleanup automation.

## Background
- Uploads persist core metadata but have no notion of when the document
  should age out.
- Operators asked for a lightweight default: expire documents after 30 days
  unless the caller specifies a custom date during upload.
- Retention knobs should live in configuration so we can tweak them per
environment.

## Scope
- Extend the document model with an `expires_at` column stored as an ISO 8601
  UTC timestamp.
- Add a configuration setting (env var `ADE_DEFAULT_DOCUMENT_RETENTION_DAYS`)
  that controls the default expiration window. Default it to 30 days.
- Update the document service to compute `expires_at` on ingest, honouring
  an optional override passed to the upload route.
- Surface the resolved `expires_at` value in the API response and ensure the
  FastAPI route accepts an optional `expires_at` form field.
- Cover the default window, the config override, and manual expiration in
  tests.

## Out of scope
- Background jobs or cron hooks that delete expired files.
- Legal hold / retention exceptions beyond a caller-provided date.
- Bulk migrations for historical uploads (manual work can handle older rows
  if needed).

## Deliverables
1. SQLAlchemy model update introducing the `expires_at` column.
2. Configuration and service changes that calculate the default or custom
   expiration timestamp when storing a document.
3. API schema + route updates exposing the new field and accepting an
   optional override during upload.
4. Pytest coverage for the default window, env-var override, and manual
   expiration path.

## Definition of done
- `expires_at` is persisted for every new upload and returned in all document
  responses.
- Uploading without an override sets expiration to `now + configured_days` and
  the default of 30 days is covered by a test.
- Providing a valid future ISO 8601 `expires_at` value stores it verbatim and
  a bad value returns a 422 explaining the issue.
- Tests exercise the new configuration knob so we know overrides behave.
