# WP9 – Contract Audit Snapshot

Generated on `2025-11-11` to capture the current contract state before the WP9 standardization refactor. This augments `wp9-standardize_models_schemas.md` with concrete inventories covering schemas, enums, wire names, pagination, and error responses.

---

## 1. Schema Audit (DTO inventory)

Legend: **Base** indicates whether the DTO currently extends `BaseSchema` or raw `BaseModel`. **ID type** calls out whether ULIDs are strongly typed. **Aliases / wire names** lists any non-canonical field exposure. **Issues / notes** summarizes why the DTO is in scope. **Target** is the proposed rename (per work package).

### Documents (`apps/api/app/features/documents/schemas.py`)

| DTO | Base | ID type | Aliases / wire names | Enum fields | Issues / notes | Target |
| --- | --- | --- | --- | --- | --- | --- |
| `UploaderSummary` | `BaseSchema` | `id: ULIDStr` (field still named `id`) | `name` alias ↔ `display_name` | N/A | Needs canonical `uploader_id`, remove alias churn. | `UploaderOut` |
| `DocumentRecord` | `BaseSchema` | `document_id: ULIDStr` alias ↔ `id`; `workspace_id: ULIDStr` | `name` alias ↔ `original_filename`; `metadata` alias ↔ `attributes`; `deleted_by` alias ↔ `deleted_by_user_id`; `tags` alias ↔ `tag_values`; `uploader` alias ↔ `uploaded_by_user` | `DocumentStatus`, `DocumentSource` | Multiple permanent aliases, `document_id` wire name not canonical, `name` vs `original_filename` mismatch. | `DocumentOut` |
| `DocumentListResponse` | `Page[DocumentRecord]` (Page uses `BaseModel`) | IDs wrapped via nested DTO | N/A | N/A | Depends on `Page` envelope; must inherit the unified base. | `Page[DocumentOut]` |

### Users (`apps/api/app/features/users/schemas.py`)

| DTO | Base | ID type | Aliases / wire names | Enum fields | Issues / notes | Target |
| --- | --- | --- | --- | --- | --- | --- |
| `UserProfile` | `BaseSchema` | `user_id: str` + alias ↔ `id`; `preferred_workspace_id: str` alias ↔ itself | alias on `user_id`; optional alias on preferred workspace | N/A | IDs are raw `str`; alias keeps `id` on wire; rename to `UserOut`. | `UserOut` |
| `UserSummary` | `BaseSchema` | inherits `UserProfile` | inherits | N/A | Could collapse into `UserOut` with additional timestamps. | `UserOut` |
| `UserListResponse` | `Page[UserSummary]` (`BaseModel`) | inherits | N/A | Page envelope not on BaseSchema. | `Page[UserOut]` |

### Workspaces (`apps/api/app/features/workspaces/schemas.py`)

| DTO | Base | ID type | Aliases / wire names | Issues / notes | Target |
| --- | --- | --- | --- | --- | --- |
| `WorkspaceProfile` | `BaseSchema` | `workspace_id: str` alias ↔ `id` | Non-canonical `id` alias; `roles`/`permissions` inline. | Should expose `workspace_id` only, rename to `WorkspaceOut`. | `WorkspaceOut` |
| `WorkspaceCreate` | `BaseSchema` | `owner_user_id: str | None` (raw) | uses explicit alias but same name | Needs `ULIDStr`, ensure default settings typed. | `WorkspaceCreate` |
| `WorkspaceUpdate` | `BaseSchema` | raw str ULIDs | N/A | Already partial, but ensure `settings` tracked as mutable JSON in ORM. | `WorkspaceUpdate` |
| `WorkspaceMemberCreate` | `BaseSchema` | `user_id: str` | N/A | Convert IDs to `ULIDStr`. | `WorkspaceMemberCreate` (same) |
| `WorkspaceMemberRolesUpdate` | `BaseSchema` | role IDs as `str` | N/A | Keep but convert IDs to alias type. | `WorkspaceMemberRolesUpdate` |
| `WorkspaceMember` | `BaseSchema` | `workspace_membership_id: str` alias ↔ `id`; nested `UserProfile` | Non-canonical alias; nested DTO to be renamed. | `WorkspaceMemberOut` |
| `WorkspaceDefaultSelection` | `BaseSchema` | `workspace_id: str` | N/A | Should rename to `WorkspaceDefaultSelectionOut`, adopt ULID alias. | `WorkspaceDefaultSelectionOut` |

### Roles & RBAC (`apps/api/app/features/roles/schemas.py`)

| DTO | Base | ID type | Aliases / wire names | Enum fields | Issues / notes | Target |
| --- | --- | --- | --- | --- | --- | --- |
| `PermissionRead` | `BaseSchema` | keys as `str` | `scope_type` literal strings | uses `Literal["global","workspace"]` | Should reference shared `PermissionScope` enum; rename to `PermissionOut`. | `PermissionOut` |
| `RoleCreate` | `BaseSchema` | `role_id` absent (create) | N/A | N/A | OK aside from ID types for permission IDs. | `RoleCreate` |
| `RoleUpdate` | `BaseSchema` | N/A | N/A | N/A | **Not partial** – `name` is required; must flip to optional fields. | `RoleUpdate` (partial) |
| `RoleRead` | `BaseSchema` | `role_id: str` alias ↔ `id` | `scope_type` literal strings | exposures rely on alias for `id`; `scope_type` should pull Enum; `scope_id` raw str. | `RoleOut` |
| `RoleAssignmentCreate` | `BaseSchema` | `role_id`, `principal_id`, `user_id` as raw str | N/A | Validation ensures either principal or user. IDs should be `ULIDStr`. | `RoleAssignmentCreate` |
| `RoleAssignmentRead` | `BaseSchema` | `assignment_id: str` alias ↔ `id`; `principal_id`, etc. raw str | `principal_type` literal `"user"` only | Should re-use enum for `PrincipalType`, canonical field names. | `RoleAssignmentOut` |
| `EffectivePermissionsResponse` | `BaseSchema` | workspace_id str | N/A | `workspace_id` optional but raw str. | keep but adopt enums/id aliasing. |
| `PermissionCheckRequest/Response` | `BaseSchema` | `workspace_id` raw str | N/A | Keep but enforces ULID. | same names |

### Auth & API keys (`apps/api/app/features/auth/schemas.py`)

| DTO | Base | ID type | Notes | Target rename |
| --- | --- | --- | --- | --- |
| `SetupStatus`, `SetupRequest`, `LoginRequest` | `BaseSchema` | raw str IDs / none | Validation helpers ok. Needs canonical ProblemDetail. | keep |
| `SessionEnvelope` | `BaseSchema` | nests `UserProfile` | Should rename to `SessionOut`, depend on `UserOut`. | `SessionOut` |
| `AuthProvider`, `ProviderDiscoveryResponse` | `BaseSchema` | provider IDs as str | ok but rename to `AuthProviderOut`, `AuthProvidersOut`. | align |
| `APIKeyIssueRequest` | `BaseSchema` | `user_id: str` | Need `ULIDStr`, rename fields? | keep |
| `APIKeyIssueResponse` | `BaseSchema` | `principal_id: str` | `principal_type` literal; should align with enum + rename to `APIKeyIssueOut`. | `APIKeyIssueOut` |
| `APIKeySummary` | `BaseSchema` | `api_key_id: str` etc. | Response used for `/api-keys` list; rename to `APIKeyOut`, adopt pagination. | `APIKeyOut` |

### Configurations & File Tree (`apps/api/app/features/configs/schemas.py`)

All DTOs currently extend raw `BaseModel` with bespoke `ConfigDict`s. None inherit `BaseSchema`, meaning inconsistent defaults and `extra="ignore"` behaviour.

Key inventory:

| DTO | Base | Issues / notes | Target |
| --- | --- | --- | --- |
| `ConfigSourceTemplate`, `ConfigSourceClone`, `ConfigSource` | `BaseModel` | Need shared base w/ discriminator + ULID validation for `config_id`. | keep names |
| `ConfigurationCreate` | `BaseModel` (extra forbid) | Should inherit `BaseSchema` (forbid), `display_name` trimming ok. | `ConfigurationCreate` |
| `ConfigurationRecord` | `BaseModel` (from_attributes) | IDs as raw str; `status` raw str; no `exclude_none` default. | `ConfigurationOut` |
| `ConfigurationValidateResponse` | `BaseModel` | same issues; rename to `ConfigurationValidateOut`. | rename |
| `ConfigurationActivateRequest` | `BaseModel` | bool flag; should land on base. | keep |
| `File*` DTOs (`FileEntry`, `FileListing`, etc.) | `BaseModel` | Several nullable fields (`mtime`, `etag`, `content_type`, `has_children`), rename `FileEntry` fields per spec; `FileRenameResponse` exports `src`/`dest` aliasing `from`/`to`. | keep names but tighten requirements |

### Builds (`apps/api/app/features/builds/schemas.py`)

| DTO | Base | Issues / notes |
| --- | --- | --- |
| `BuildRecord` | `BaseModel` (`from_attributes=True`) | IDs raw str; `status` uses `BuildStatus` but column stored as str; exposes `venv_path` absolute path; lacks `extra="forbid"` defaults. |
| `BuildEnsureRequest` | `BaseModel` (`extra="forbid"`) | Should inherit `BaseSchema` so defaults consistent. |
| `BuildEnsureResponse` | `BaseModel` | Implements custom `model_dump` to exclude `None`; unify via base + `exclude_none`. |

### Jobs (`apps/api/app/features/jobs/schemas.py`)

Single `JobPlaceholder(BaseModel)` with `id: str`. Needs real DTO or removal.

### Shared pagination (`apps/api/app/shared/pagination.py`)

`PageParams` and `Page` inherit `BaseModel`. `Page` exposes `{items,page,page_size,has_next,has_previous,total}`; lacks `count`/`next_token`. Should move to unified base + align envelope spec.

### Other cross-cutting items

- `BaseSchema` config ( `apps/api/app/shared/core/schema.py` ) currently sets `extra="ignore"` and `use_enum_values=True`. WP9 requires `extra="forbid"`, `from_attributes=True`, `populate_by_name=True`, and default `model_dump(exclude_none=True)` semantics without overriding `use_enum_values`.
- `ErrorMessage` schema is the shared error envelope; returns `{"detail": ...}` which conflicts with the desired `ProblemDetail`.
- `ULIDStr` alias is defined only inside `apps/api/app/features/documents/filters.py` and not exported for other modules.
- `Workspace.settings` (`apps/api/app/features/workspaces/models.py:15-23`) uses plain JSON without `MutableDict`, so in-place mutations are not tracked.

---

## 2. Enum Catalog (current vs target)

| Concept | Current implementation | Current values / source | Target Enum & usage | Notes |
| --- | --- | --- | --- | --- |
| `Configuration.status` | Plain `String(20)` column + string comparisons in `service.py` (`draft`, `active`, `inactive`) | `apps/api/app/features/configs/models.py:25-36` | New `ConfigurationStatus(str, Enum)` (likely `draft`, `published`, `archived`) used in ORM column (`Enum(..., native_enum=False)`) and every schema field. | Need migration to reconcile `active` vs `published`. |
| `Build.status` | Column stored as `String` w/ `CheckConstraint`; Python `BuildStatus` Enum already exists but not enforced in DB layer. | `apps/api/app/features/builds/models.py:20-78` | Reuse `BuildStatus` for SQLAlchemy `Enum` + Pydantic field; ensure `Page` etc. emit string enums. | Replace raw `Mapped[str]` with `Mapped[BuildStatus]`. |
| `Document.status` | Stored as string with `CheckConstraint` but `DocumentStatus(str, Enum)` exists. | `apps/api/app/features/documents/models.py:20-78` | Switch columns to SQLAlchemy Enum using existing class; share same Enum via schemas/filters. | Already imported in schemas. DB type change needed. |
| `Document.source` | Same as above with `DocumentSource`. | Single value `manual_upload`. | Same as above; future expansion easier. |
| `RBAC scope_type` | SQLAlchemy `Enum` objects (`ScopeTypeEnum`, `PrincipalTypeEnum`) without Python Enum types surfaced at schema layer. | `global`, `workspace` for scope; `user` for principal. | Introduce `ScopeType(str, Enum)` / `PrincipalType(str, Enum)` used across ORM + schemas. | Align `PermissionRead`, `Role*`, `RoleAssignment*`. |
| `Document/File depth` | `Literal["0","1","infinity"]` in `FileListing.depth`. | Hardcoded union. | Keep as `Literal` or convert to Enum if we need `Depth`. Must align request + response. |
| `ProblemDetail.code` | In configs router only; string codes like `config_not_found`. | `_problem` helper. | Normalize via shared `ProblemCode` enum or curated registry referenced by `ProblemDetail`. | Need table of codes. |

---

## 3. Wire Name Map (fields with aliases to deprecate)

| Field (current DTO) | File | Current wire name(s) | Canonical target | Deprecation note |
| --- | --- | --- | --- | --- |
| `DocumentRecord.document_id` | `apps/api/app/features/documents/schemas.py` | exposes both `id` & `document_id` | keep `document_id` only (ULIDStr) | Remove alias; accept legacy `id` for one release via deprecated alias. |
| `DocumentRecord.name` vs `original_filename` | same | alias/serialize mismatch | Keep `original_filename` on wire; drop `name` alias. | Add computed property for compatibility if needed. |
| `DocumentRecord.metadata` | same | alias ↔ `attributes` | Keep `metadata` or `attributes`, not both. | Document alias removal plan. |
| `DocumentRecord.deleted_by` | same | alias ↔ `deleted_by_user_id` | Use `deleted_by_user_id`. |  |
| `DocumentRecord.tags` | same | alias ↔ `tag_values` | Keep `tags`. |  |
| `UploaderSummary.id/name` | same | `id` + alias for `display_name` | Rename to `uploader_id`, keep `display_name`. |  |
| `UserProfile.user_id` | `apps/api/app/features/users/schemas.py` | alias ↔ `id` | Only expose `user_id`; remove alias. |  |
| `WorkspaceProfile.workspace_id` | `apps/api/app/features/workspaces/schemas.py` | alias ↔ `id` | Keep `workspace_id`. |  |
| `WorkspaceMember.workspace_membership_id` | same | alias ↔ `id` | Keep `workspace_membership_id`. |  |
| `RoleRead.role_id` | `apps/api/app/features/roles/schemas.py` | alias ↔ `id` | Keep `role_id`. |  |
| `RoleAssignmentRead.assignment_id` | same | alias ↔ `id` | Keep `assignment_id`. |  |
| `FileRenameResponse.src/dest` | `apps/api/app/features/configs/schemas.py` | `src`/`dest` fields alias `from`/`to` | Rename actual fields to `from_path` / `to_path` or keep `from`/`to` as canonical wire keys. | Should mark `src`/`dest` deprecated. |

*(Add more rows as additional aliases are discovered during implementation.)*

---

## 4. List Envelope Map (endpoints returning raw arrays)

All endpoints below currently declare `response_model=list[...]` and should adopt `Page[T]` (or `{Resource}List` alias) with uniform `{items, page, page_size, has_next, has_previous, total}` or the new canonical envelope.

| Endpoint | Module / file | Current model | Notes |
| --- | --- | --- | --- |
| `GET /roles` | `apps/api/app/features/roles/router.py:225` | `list[RoleRead]` | Should become `Page[RoleOut]` with sort/filter query params. |
| `GET /role-assignments` | `roles/router.py:482` | `list[RoleAssignmentRead]` | Add pagination + filtering (principal_id/user_id). |
| `GET /workspaces/{workspace_id}/role-assignments` | `roles/router.py:644` | `list[RoleAssignmentRead]` | Same as above, workspace-scoped. |
| `GET /permissions` | `roles/router.py:830` | `list[PermissionRead]` | Could remain list if bounded, but spec calls for Page envelope. |
| `GET /auth/api-keys` | `auth/router.py:412` | `list[APIKeySummary]` | Convert to `Page[APIKeyOut]`, add filters (revoked, owner). |
| `GET /workspaces` | `workspaces/router.py:106` | `list[WorkspaceProfile]` | Response should be paged for multi-workspace orgs. |
| `GET /workspaces/{workspace_id}/members` | `workspaces/router.py:165` | `list[WorkspaceMember]` | Need pagination & filtering (role, default). |
| `GET /workspaces/{workspace_id}/roles` | `workspaces/router.py:200` | `list[RoleRead]` | Should re-use `Page[RoleOut]`. |
| `GET /workspaces/{workspace_id}/configurations` | `configs/router.py:141` | `list[ConfigurationRecord]` | Convert to `Page[ConfigurationOut]`. |

*(Documents and users already use `Page[T]`.)*

---

## 5. Error Model Inventory

- **Global default**: Routers import `ErrorMessage` from `apps/api/app/shared/core/schema.py`, yielding FastAPI’s `{"detail": "..."}`
  - files: `auth/router.py`, `builds/router.py`, `documents/router.py`, `workspaces/router.py`, `configs/router.py` (in addition to custom problem helper).
- **Configs module**: `_problem()` helper already emits RFC 7807-ish payloads with `type`, `title`, `status`, `detail`, `code`, `meta`.
- **Missing pieces**: No shared `ProblemDetail` schema; no registry of stable `code` values; routers mix literal strings vs dicts in `HTTPException.detail`.

**Action**: introduce `ProblemDetail(BaseSchema)` with RFC‑9457 fields (`type`, `title`, `status`, `detail`, `instance?`, plus `code`, `trace_id`, `meta`). Replace `ErrorMessage` references and standardize `_problem()` to instantiate `ProblemDetail`. Update OpenAPI components/responses accordingly.

---

## 6. ULID Type Alias Coverage

- Only `apps/api/app/features/documents/filters.py` defines `ULIDStr = Annotated[str, Field(..., pattern=ULID_PATTERN)]`.
- All other schemas (`users`, `workspaces`, `roles`, `auth`, `configs`, `builds`) use raw `str` for ULIDs. No shared module exports ULID validators.

**Action**: move `ULID_PATTERN` and `ULIDStr` into a shared module (e.g., `apps/api/app/shared/core/ids.py` or `shared/core/types.py`) and import everywhere. Update ORM mixins to surface type hints when constructing DTOs.

---

## 7. Workspace Settings Mutability

- `Workspace.settings` is declared as `JSON` without `MutableDict` (`apps/api/app/features/workspaces/models.py:14-24`). Updating nested keys in-place will not mark the row dirty, causing silent data loss.
- `Document.attributes` and `SystemSetting.value` already use `MutableDict`.

**Action**: migrate column to `MutableDict.as_mutable(JSON)` with Alembic backfill, update services/tests accordingly.

---

## 8. Build Surface Hardening

- `BuildRecord` DTO exposes `venv_path` (absolute host path). REST responses leak host filesystem layout.
- `ConfigurationBuild` ORM stores `venv_path` as `Text`.

**Action**: add `environment_ref` / `venv_label` that maps to user-friendly handle; continue storing `venv_path` internally but omit from responses. Provide transitional alias (deprecated) if needed.

---

## 9. OpenAPI & Codegen Plan

Pending refactor steps:

1. Update schemas/enums/routers per sections above.
2. Run `npm run openapi-typescript` to ensure the generated client surfaces string enums and discriminated unions without `any`.
3. Capture before/after spec (e.g., `apps/api/app/openapi.json`) to aid reviewers.

---

## 10. Next Steps Checklist

- [ ] Update `BaseSchema` config + migrate all DTOs (configs, builds, jobs, pagination) to inherit from it.
- [ ] Introduce shared `ULIDStr` + update every `*_id` field.
- [ ] Define canonical enums + apply to ORM columns and schemas.
- [ ] Make every `*Update` schema partial (notably `RoleUpdate`).
- [ ] Remove permanent aliases per the wire-name map with temporary deprecated aliases when needed.
- [ ] Convert raw list endpoints to the standardized `Page[T]` envelope.
- [ ] Tighten file tree DTOs (required metadata, `inode/directory`, rename response keys).
- [ ] Replace `venv_path` with sanitized field.
- [ ] Introduce `ProblemDetail` and drop `ErrorMessage`.
- [ ] Switch `Workspace.settings` to `MutableDict`.

This document should evolve alongside the implementation to track which gaps have been closed.

---

## 11. Implementation Plan (draft)

1. **Core primitives first**
   - Update `BaseSchema` defaults (extra forbid, populate by name, from_attributes, `exclude_none=True`) and migrate `Page`, `PageParams`, `FilterBase`, configs/builds/jobs schemas to inherit from it.
   - Create `apps/api/app/shared/core/types.py` (or extend `shared/core/ids.py`) with shared `ULID_PATTERN` + `ULIDStr` and begin replacing raw `str` annotations across schemas, filters, services.
2. **Enum + ORM alignment**
   - Define `ConfigurationStatus`, `ScopeType`, `PrincipalType`, and move SQLAlchemy columns to use `Enum(..., native_enum=False)` referencing the Python `Enum`.
   - Update migrations + repositories/services accordingly; adjust `BuildStatus` / `DocumentStatus` columns to store Enum values natively.
3. **DTO renames & contract cleanup**
   - Rename DTOs to `*Out`, collapse `UserProfile/UserSummary`, `DocumentRecord`, `WorkspaceProfile`, `RoleRead`, etc.; update `__all__` exports and imports in routers/services.
   - Remove permanent aliases per the wire-name map; add temporary deprecated aliases with `Field(serialization_alias=..., deprecated=True)` when required.
   - Make every `*Update` schema optional-field-only (notably `RoleUpdate`).
4. **Pagination standardization**
   - Extend `Page[T]` to include requested canonical fields (`items`, `count`/`total`, `next_token` if applicable) and update `paginate_sql/sequence`.
   - Convert all list endpoints in the map to return `Page[...]`, adding sort/filter params where missing.
5. **File tree tightening**
   - Update `FileEntry` to require `mtime`, `etag`, `content_type`, `has_children`; enforce `content_type="inode/directory"` for directories and `size=None` rule.
   - Rename `FileRenameResponse` wire keys to `from`/`to` with deprecated `src`/`dest` bridge.
6. **Build + workspace storage safeguards**
   - Replace `BuildRecord.venv_path` with `environment_ref` (plus temporary alias if needed).
   - Update ORM + service to populate the new field; scrub path exposure from routers/tests.
   - Change `Workspace.settings` to `MutableDict.as_mutable(JSON)` with Alembic migration + regression tests covering in-place mutation.
7. **Problem Details**
   - Implement shared `ProblemDetail` schema + helper for raising errors; update routers to reference it in `responses` metadata.
   - Convert configs `_problem()` to return the shared schema; drop `ErrorMessage`.
8. **Contract verification**
   - Refresh OpenAPI schema + run `npm run openapi-typescript`; add regression tests for DTO serialization (golden fixtures) and alias deprecation.
   - Ensure CI covers new pagination/list tests, back-compat alias acceptance, and sanitized build responses.
