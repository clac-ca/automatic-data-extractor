# Documents Section (List + Detail)

## UX model (quick summary)

- The documents list is the primary surface.
- Clicking a document opens a **document detail page** ("ticket view") for that document.
- The detail page is **activity-first**:
  - `tab=activity` is the default document landing view.
  - `tab=preview` is the dedicated preview workspace.
- Preview source is explicit:
  - `source=normalized` (default)
  - `source=original`
- Normalized preview does **not** auto-fallback to original when unavailable.

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
  - `tab` — active tab (`activity` default, `preview`)
  - `activityFilter` — activity feed filter (`all`, `comments`, `events`)
  - `source` — preview source (`normalized`, `original`; only used for `tab=preview`)
  - `sheet` — selected sheet name (only used for `tab=preview`)

### Legacy (deprecated)

- `tab=data` -> `tab=preview`
- `tab=comments` -> `tab=activity&activityFilter=comments`
- `tab=timeline` -> `tab=activity&activityFilter=events`

## Data sources

- Activity tab:
  - Comments: `/documents/{documentId}/comments` (list + create)
  - Run history: `fetchWorkspaceRunsForDocument`
- Preview tab:
  - Original: `fetchDocumentSheets` + `fetchDocumentPreview`
  - Normalized: `fetchRunOutputSheets` + `fetchRunOutputPreview`
