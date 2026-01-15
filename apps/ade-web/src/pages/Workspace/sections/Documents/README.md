# Documents Section (Preview + Comments)

## UX model (quick summary)

- The documents list is the primary surface.
- Clicking a document name opens a **bottom split-pane preview** immediately.
- Comments open in a **right-side panel** and can be shown alongside the preview.
- Panels are resizable using `react-resizable-panels`.
- Preview is read-only and uses DiceUI `data-table` components.

## URL query keys

These keys are owned by the Documents section:

- `docId` — selected document id
- `panes` — comma-separated `"preview"` / `"comments"` list of open panels
- `filterFlag` — `"advancedFilters"` toggle for the list toolbar

## Data sources

- Preview: `fetchDocumentSheets` + `fetchDocumentPreview`
- Comments: `/documents/{documentId}/comments` (list + create)
