# Documents Section (List + Detail)

## UX model

- The list is the intake surface; the detail page is the focused workspace.
- Detail uses a ticket-style IA:
  - `Activity` is the default and primary collaboration surface.
  - `Preview` is explicit and task-oriented.
- Preview is source-aware:
  - `Normalized` is default.
  - `Original` is opt-in only.
  - No automatic source fallback.

## Visual/interaction principles

- Sticky document header with identity, run status, and download actions.
- Activity feed has a mixed timeline (upload, runs, comments) with filter chips.
- Comment composer stays pinned at the bottom of Activity.
- Preview is spreadsheet-first:
  - tabular grid with row/column cues
  - source switch in header
  - sheet selector anchored at the bottom

## Routing

The Documents section is split into two screens:

- List: `/workspaces/:workspaceId/documents`
- Detail: `/workspaces/:workspaceId/documents/:documentId`

## URL query keys

These query keys are owned by the Documents section:

- List:
  - `q` - search query
  - `filterFlag` - `"advancedFilters"` toggle for the list toolbar
- Detail:
  - `tab` - active tab (`activity` default, `preview`)
  - `activityFilter` - activity feed filter (`all`, `comments`, `events`)
  - `source` - preview source (`normalized`, `original`; only used for `tab=preview`)
  - `sheet` - selected sheet name (only used for `tab=preview`)

Only canonical keys above are supported.

## Data sources

- Activity tab:
  - Comments: `/documents/{documentId}/comments` (list + create)
  - Run history: `fetchWorkspaceRunsForDocument`
- Preview tab:
  - Original: `fetchDocumentSheets` + `fetchDocumentPreview`
  - Normalized: `fetchRunOutputSheets` + `fetchRunOutputPreview`

## Code architecture

- URL state lives in:
  - `detail/hooks/useDocumentDetailUrlState.ts`
  - `shared/navigation.ts`
- Detail page is orchestration-only:
  - `detail/DocumentsDetailPage.tsx`
- Activity is split into shell + model + presentational components:
  - `tabs/activity/hooks/useDocumentActivityFeed.ts`
  - `tabs/activity/model.ts`
  - `tabs/activity/components/*`
- Preview is split into shell + model + presentational components:
  - `tabs/preview/hooks/useDocumentPreviewModel.ts`
  - `tabs/preview/components/*`
