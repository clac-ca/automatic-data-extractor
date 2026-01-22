# Documents Section (Preview + Comments)

## UX model (quick summary)

- The documents list is the primary surface.
- Clicking a document name opens a **full-screen preview dialog** immediately.
- Comments open in a **right-side panel** on the list view.
- Preview is read-only and uses Glide Data Grid.

## URL query keys

These keys are owned by the Documents section:

- `docId` — selected document id
- `panes` — comma-separated `"preview"` / `"comments"` list of open panels
- `filterFlag` — `"advancedFilters"` toggle for the list toolbar

## Data sources

- Preview: `fetchDocumentSheets` + `fetchDocumentPreview`
- Comments: `/documents/{documentId}/comments` (list + create)
