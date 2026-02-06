# Documents Section (List + Detail)

## UX model (quick summary)

- The documents list is the primary surface.
- Clicking a document opens a **document detail page** ("ticket view") for that document.
- The detail page owns tabs like **Data** (preview grid), **Comments**, and **Timeline**.
- Data preview is read-only and uses Glide Data Grid.

## Routing

The Documents section is split into two screens:

- List: `/workspaces/:workspaceId/documents`
- Detail: `/workspaces/:workspaceId/documents/:documentId`

## URL query keys

These query keys are owned by the Documents section:

- List:
  - `q` — search query
  - `filterFlag` — `"advancedFilters"` toggle for the list toolbar
- Detail:
  - `tab` — active tab (`data` default, `comments`, `timeline`)

### Legacy (deprecated)

None.

## Data sources

- Data tab (preview): `fetchDocumentSheets` + `fetchDocumentPreview`
- Comments tab: `/documents/{documentId}/comments` (list + create)
