# Completed task – Workspace documents ingestion UI

## Outcome
- Added typed API clients and React Query hooks for workspace documents and active configurations with shared normalisers, upload, and delete helpers.
- Replaced the documents placeholder with a full workflow: document-type selector with localStorage persistence, drag-and-drop uploads, advanced metadata/configuration overrides, and a responsive documents table with download/metadata/delete actions.
- Introduced formatting utilities, modal and table styling, and Vitest coverage for document hooks plus dropzone behaviour to keep the workflow reliable.

## Next steps
- Surface the selected document-type filter in the global top bar so the list, jobs, and results remain in sync.
- Build the workspace jobs slice (submission, list, detail) using the new configuration and document helpers.
- Add smoke tests around the sign-in flow now that authenticated interactions hit live endpoints.
