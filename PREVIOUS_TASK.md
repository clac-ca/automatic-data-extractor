## Context
Phase 4 continued by wiring document metadata editing into the rebuilt documents module.

## Outcome
- Added a `DocumentMetadataUpdateRequest` schema and `DocumentsService.update_document_metadata` helper that merges changes, removes cleared keys, emits diff-aware events, and accepts optional event overrides.
- Exposed a guarded `PATCH /documents/{document_id}` route that mirrors upload permissions, publishes `document.metadata.updated` events, and propagates custom event types/payloads to the message hub and timeline.
- Expanded integration coverage to assert metadata merge/remove behaviour, custom event overrides, permission enforcement, and missing-document responses while validating hub payloads and timeline diffs.
