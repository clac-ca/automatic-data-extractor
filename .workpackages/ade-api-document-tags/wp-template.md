> **Agent Instructions (read first)**
>
> * Treat this work package as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` -> `[x]` as tasks are completed.
> * Prefer small, incremental commits aligned to checklist items.
> * If the plan must change, **update this document first**, then update the code.

---

No backward compatibility. Replace existing tag filters and update all callers.

## What we are fundamentally doing

We are making document tags a first-class API feature with standard naming, behavior, and query syntax:

* Normalize and validate tags consistently on write and filter input.
* Provide explicit tag management endpoints (replace and patch).
* Provide a tag catalog endpoint for search and counts.
* Provide unambiguous tag filters using a standard query shape.

---

## Work Package Checklist

* [x] Finalize tag normalization + validation rules (length, case, whitespace, max tags per doc). - helper + validators in filters/service.
* [x] Backend: replace `tags_in` with `tags` + `tags_match` query syntax. - filters + callers updated.
* [x] Backend: add tag update endpoints (`PUT/PATCH /documents/{id}/tags`) with atomic updates. - router/service implemented.
* [x] Backend: add tag catalog endpoint (`GET /workspaces/{id}/tags`) with counts + search. - router/service implemented.
* [x] Backend: implement tag filters (`tags`, `tags_match`, `tags_not`, `tags_empty`). - apply_document_filters updated.
* [x] Backend: update DB schema/indexes for tag queries. - migration + model updates.
* [x] Tests: cover normalization, updates, catalog counts, and filter semantics. - integration tests added/updated.
* [x] Docs + clients: update API docs and all callers to the new tag filter syntax. - OpenAPI regen + frontend API usage.

> **Agent note:**
> Keep brief status notes inline, for example:
> `- [x] Add tag update endpoints - <commit or short note>`

---

# ADE Document Tags (Standard)

## 1. Objective

**Goal:**
Implement standard, predictable tag behavior and query syntax with no backward compatibility.

You will:

* Define canonical normalization and validation rules.
* Expose tag management endpoints and a tag catalog endpoint.
* Replace the document tag filter syntax with a standard pattern.

The result must:

* Allow clients to set, replace, and remove tags explicitly.
* Provide deterministic tag output (sorted).
* Support efficient any/all/not/empty tag filtering.

---

## 2. Non-negotiable decisions

* **No backward compatibility.** Remove `tags_in` and update all callers.
* **Canonical field name:** `DocumentOut.tags`.
* **Filter syntax:**
  * `tags` - list of tag strings (CSV or repeated query params).
  * `tags_match` - `any` (default) or `all` (only applies to `tags`).
  * `tags_not` - exclude documents with any of these tags.
  * `tags_empty` - boolean; when `true`, only untagged documents are returned.
* **Normalization rules (applied everywhere):**
  * Strip control characters.
  * Trim leading/trailing whitespace.
  * Collapse internal whitespace to a single space.
  * Lowercase via `casefold()`.
  * Reject empty tags after normalization.
* **Limits:**
  * Max tag length: 100 chars (post-normalization).
  * Max tags per document: 50.
* **Output ordering:** `DocumentOut.tags` is sorted ascending.
* **Tag catalog:** excludes soft-deleted documents.

---

## 3. API contracts (authoritative)

### 3.1 Replace tags

`PUT /api/v1/workspaces/{workspace_id}/documents/{document_id}/tags`

Request:

```json
{ "tags": ["finance", "q1-report", "priority"] }
```

Response:

* `200 DocumentOut` with updated `tags`.
* `404` if document not found.
* `422` if validation fails.

### 3.2 Patch tags

`PATCH /api/v1/workspaces/{workspace_id}/documents/{document_id}/tags`

Request:

```json
{ "add": ["finance"], "remove": ["draft"] }
```

Rules:

* `add` and `remove` are both optional.
* Reject requests where both are empty or missing (`422`).

Response:

* `200 DocumentOut` with updated `tags`.
* `404` if document not found.
* `422` if validation fails.

### 3.3 Tag catalog

`GET /api/v1/workspaces/{workspace_id}/tags`

Query params:

* `q` - optional search string, minimum length 2.
* `page`, `page_size`, `include_total` - standard paging.
* `sort` - `name` (default) or `-count`.

Response:

```json
{
  "items": [
    { "tag": "finance", "document_count": 12 },
    { "tag": "priority", "document_count": 7 }
  ],
  "page": 1,
  "page_size": 25,
  "has_next": false,
  "has_previous": false,
  "total": 2
}
```

### 3.4 Document filters

`GET /api/v1/workspaces/{workspace_id}/documents`

Rules:

* `tags` accepts CSV or repeated params.
* `tags_match` is required only when `tags` is provided; default is `any`.
* `tags_not` accepts CSV or repeated params.
* If `tags_empty=true`, then `tags` and `tags_not` must be absent (else `422`).

---

## 4. Data model and indexes

* `document_tags` is the backing store for tags.
* Add `id` PK and keep `UNIQUE(document_id, tag)` for standard PK naming.
* Keep existing indexes on `document_id` and `tag`.
* Add composite index `(tag, document_id)` to speed catalog and filters.

---

## 5. Implementation notes

* Update router filter allowlists to remove `tags_in`.
* Implement a shared normalization helper and reuse it in filters and write endpoints.
* Apply tag updates atomically in a single transaction.
* Update all clients and tests to use `tags` + `tags_match`.

---

## 6. Test plan

1. **Normalization**
   * whitespace trimming, collapse, casefolding, control-char removal.
   * rejects empty or over-length tags.
2. **Tag updates**
   * `PUT` replaces tags exactly (idempotent).
   * `PATCH` add/remove is idempotent and does not duplicate.
3. **Tag catalog**
   * counts are correct and exclude soft-deleted documents.
   * sorting by name and by count works.
4. **Filters**
   * `tags` + `tags_match` any/all behavior.
   * `tags_not` excludes matches.
   * `tags_empty=true` only returns untagged documents.

---

## 7. Non-goals

* Tag metadata (color, description, owner).
* Tag rename/merge operations across documents.
* Cross-resource tags (runs, configs, etc.).
* UI for tag management (separate workpackage).
