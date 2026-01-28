# Work Package: Frontend Documents Realtime Integration

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Integrate the document change stream into the Documents screen by listening to SSE notifications, pulling deltas, and patching visible rows via the list endpoint with `id` filters. Keep URL-based filters and cursor pagination as the source of truth, and avoid disruptive page shifts.

### Problem Statement and Resolution

**Problem:** With cursor pagination and server-side filters, a change notification can tell us a document changed, but it does not tell us whether the document belongs to the current **page window** or where it should be positioned. Inserting blindly can shift rows and make page N inconsistent with the server's ordering.

**Resolution:** Use the list endpoint with `id in [...]` plus current filters to confirm **membership**. If the document is already on the page, update it; if it belongs but is not visible, mark the view as **stale** and show an "updates available" indicator. Only page 1 performs live insert+evict; page N never infers position without a full page refresh.

### Research References (read first)

- `workpackages/wp-document-stream-refactor/research.md` lines 687-786 (frontend SSE + delta + list(id) flow)
- `workpackages/wp-document-stream-refactor/research.md` lines 788-800 (reconciliation rules for page 1 vs page N)
- `workpackages/wp-document-stream-refactor/research.md` lines 806-839 (pagination UX rules + mutable sort handling)
- `workpackages/wp-document-stream-refactor/research.md` lines 971-978 (frontend checklist)

### Scope

- In: SSE subscription, delta polling, list membership reconciliation, UI stale indicators, page-1 live updates.
- Out: new list API, major UX redesign, cross-workspace streams, realtime totals/facets.

### Work Breakdown Structure (WBS)

0.1 Research review
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 687-786 (frontend code examples: SSE + delta + list(id) fetch)
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 788-839 (pagination UX rules + reconciliation)
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 923-929 (load/burst batching guidance)
1.0 Client state and plumbing
  1.1 Token management
    - [ ] Track delta token in memory (and optional sessionStorage) (Research: lines 274-292, 691-693)
    - [ ] Reset token when filters/sort/query change (Research: lines 691-693)
  1.2 SSE subscription
    - [ ] Update stream URL to `/documents/stream` (Design decision)
    - [ ] Add EventSource for `/documents/stream` (Research: lines 187-197; code example lines 706-715)
    - [ ] Debounce delta pulls on notifications (Research: lines 717-731; code example lines 721-731)
    - [ ] Confirm auth approach for SSE (cookie-based EventSource) (Research: lines 697-702)
    - [ ] Update event parsing to minimal payload `{documentId, op, token}` (Design decision)
    - [ ] Remove includeRows/include param handling from stream URL builder (Design decision)
    - [ ] Remove row-based update handling from stream consumers (Design decision)
    - [ ] Prefer `event.lastEventId` when payload lacks token (Design decision)
2.0 Delta + list membership integration
  2.1 Delta fetch
    - [ ] Call `/documents/delta` and update token (Research: lines 201-215; code example lines 738-750)
    - [ ] Handle 410 by forcing page refresh (Research: lines 218-221; code example lines 743-746)
    - [ ] Loop while `hasMore` to exhaust delta pages (Research: lines 201-215)
    - [ ] Wire delta polling into WorkspaceDocumentsStreamContext (Design decision)
  2.2 Membership fetch via list endpoint
    - [ ] Call `/documents` with current filters plus `id in [...]` (Research: lines 223-239; code example lines 762-780)
    - [ ] Apply deletes and patch rows by id (Research: lines 760-780, 792-800)
    - [ ] Deduplicate IDs and batch requests on bursty updates (Research: lines 717-786, 923-929)
    - [ ] Add inline comment explaining we reuse the list endpoint for authoritative filter semantics (Design decision)
3.0 Pagination UX rules
  3.1 Page 1 live updates
    - [ ] Insert/replace visible rows when in window (Research: lines 792-795, 816-817)
    - [ ] Evict to maintain page size (Research: lines 795-795)
  3.2 Page N updates
    - [ ] Avoid shifting membership (Research: lines 810-817)
    - [ ] Show "updates available" indicator and allow refresh (Research: lines 799-800, 816-817) (Design decision: page N uses stale indicator)
    - [ ] Use list(id filter) only to confirm membership; do not infer exact position without full page refresh (Design decision)
  3.3 Sort edge cases
    - [ ] Handle mutable sort keys (activityAt) without reshuffling page N (Research: lines 819-827)
4.0 Side bar and secondary views
  4.1 Sidebar updates
    - [ ] Decide whether sidebar uses same stream or separate view logic
    - [ ] Apply changes using list(id filter) membership checks
    - [ ] Remove direct row payload usage in sidebar updates (Design decision)

### Open Questions

- Should the sidebar consume the same stream or an isolated stream instance? (Research: lines 123-129, 687-693)
- What is the preferred stale indicator UI (banner, badge, or toast)? (Research: lines 799-800, 816-817)

---

## Acceptance Criteria

- Documents table updates visible rows with minimal jank. (Research: lines 792-800, 816-827)
- Non-visible changes do not force full refresh; stale indicator is shown. (Research: lines 799-800, 816-817)
- 410 resync triggers a full page refetch. (Research: lines 218-221, 743-746)

---

## Definition of Done

- SSE + delta + list(id filter) wired into Documents screen. (Research: lines 687-786, 961-978)
- URL-based filters remain the source of truth for the page query. (Research: lines 51-67, 691-693)
- UI behavior matches the agreed rules for page 1 vs page N. (Research: lines 792-817, 806-827)
