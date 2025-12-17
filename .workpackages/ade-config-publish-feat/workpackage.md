> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

- [ ] Align lifecycle terminology (Draft / Active / Archived) across UI + API.
- [ ] Enforce “single active config per workspace” at the DB level (partial unique index).
- [ ] Implement “Make active” UX (draft → active, auto-archive previous active).
- [ ] Implement archive UX (active → archived) with confirmation + clear impact.
- [ ] Implement duplicate UX (any → new draft copy) for rollback/editing.
- [ ] Make workbench explicitly read-only for non-draft configs (with “Duplicate to edit” CTA).
- [ ] Default Documents “Run extraction” to the active config (still allow override).
- [ ] Add frontend API helpers/hooks for make-active (publish) + duplicate; wire to UI.
- [ ] Update docs + regenerate frontend OpenAPI types (`ade types`) after API changes.
- [ ] Add targeted tests (backend lifecycle + frontend minimal coverage).

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] {{CHECK_TASK_1_SUMMARY}} — {{SHORT_STATUS_OR_COMMIT_REF}}`

---

# Config publishing + lifecycle UX (single active config)

## 1. Objective

Build a first-class, intuitive workflow for managing ADE configuration packages as versions within a workspace:

- Exactly **one** configuration is **Active** at any time.
- Unlimited **Draft** and **Archived** configurations.
- **Only Draft** configurations are editable.
- “Rollback” is done by **duplicating** a previous config into a new **Draft**, then **making it active**.

The UX should make the lifecycle obvious and safe: users can always answer “which config is live?” and “how do I change it safely?”.

---

## 2. Assessment (current conditions)

### 2.1 Backend (already exists, not surfaced in UX)

Key implementation exists today:

- Model: `apps/ade-api/src/ade_api/models/configuration.py`
  - Status enum includes: `draft`, `published`, `active`, `inactive`.
- Lifecycle routes: `apps/ade-api/src/ade_api/features/configs/endpoints/configurations.py`
  - `GET  /api/v1/workspaces/{workspace_id}/configurations`
  - `POST /api/v1/workspaces/{workspace_id}/configurations` (supports `source: template|clone`)
  - `POST /api/v1/workspaces/{workspace_id}/configurations/{id}/validate`
  - `POST /api/v1/workspaces/{workspace_id}/configurations/{id}/publish` (draft → published; not active)
  - `POST /api/v1/workspaces/{workspace_id}/configurations/{id}/activate` (draft/published/inactive → active)
  - `POST /api/v1/workspaces/{workspace_id}/configurations/{id}/deactivate` (→ inactive; comment says “was archive”)
- Edit protection: file writes are blocked unless status is `draft` (`_ensure_editable_status` in `apps/ade-api/src/ade_api/features/configs/service.py`).

Gaps/risks:

- No DB-level enforcement for “only one active per workspace” (docs call for a partial unique index).
- Status naming and semantics drift (`inactive` vs `archived`; unclear purpose for `published`).

### 2.2 Frontend (lifecycle UX is missing)

Current UI supports create/import/export and workbench editing, but does not expose lifecycle controls:

- Config list: `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/index.tsx`
  - Create from template + import ZIP.
  - No **Duplicate**, **Make active**, or **Archive** actions.
- Config detail page is placeholder: `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/detail/index.tsx`
- Workbench has validation/test runs + zip export/import, but no lifecycle actions:
  - `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx`
- API helpers exist for `activate`/`deactivate` but are unused; `publish` helper is missing:
  - `apps/ade-web/src/shared/configurations/api.ts`

Result: users can create/edit drafts but cannot make a config “live”, archive it, or safely rollback via duplication.

### 2.3 Product intent (source of truth)

- `docs/developers/design-decisions/dd-0002-single-active-config.md`: exactly one active config per workspace; others draft/archived.

This workpackage implements that lifecycle in UX and reconciles backend naming/constraints accordingly.

---

## 3. Target lifecycle model (user-facing)

### 3.1 States (canonical UX terms)

- **Draft** — editable; can be validated; can be made active.
- **Active** — read-only; used as the workspace’s live configuration.
- **Archived** — read-only; historical record.

### 3.2 Rules

- Exactly one **Active** config per workspace (enforced in DB and service).
- Only **Draft** can be edited (API already enforces; UX must make it explicit).
- Rollback/edit is always: **Duplicate → Draft → Make active**.

### 3.3 Transitions (state machine)

```text
Draft --(Make active)--> Active --(Archive)--> Archived
  ^                      |
  |                      |
  +------(Duplicate)-----+   (Duplicate is available from any state)
```

---

## 4. Design (UX + API)

### 4.0 UX principles (small details that make it feel intuitive)

- **Make the “safe path” the easiest path**: the obvious next step is always the correct one (Draft → Make active; Active/Archived → Duplicate to edit).
- **One primary action per surface**: avoid button soup; move secondary actions into an overflow menu.
- **Explain disabled states**: when actions are unavailable (read-only, missing permissions), show short, specific reasons.
- **Prevent surprises**: lifecycle actions that affect the workspace (Make active, Archive) always confirm and clearly state impact.
- **Stay oriented**: highlight Active, use clear labels, and avoid sudden navigation unless it reduces confusion (e.g., jump to the new draft after duplicating).
- **Accessible by default**: keyboard-first flows (focus management, Escape to close, Enter to confirm), clear `aria-live` messaging for async toasts/errors, and sufficient contrast for status chips.

### 4.1 UX information architecture

```text
Workspace → Configuration Builder
  - Configurations list (Active / Drafts / Archived)
  - Configuration details (metadata + lifecycle actions)
  - Workbench editor (edit/validate/test; read-only when non-draft)
```

### 4.2 Configurations list UX

Primary structure: three grouped sections (or tabs) in priority order:

1) **Active configuration** (single card)
2) **Drafts**
3) **Archived**

Each config row/card shows:

- Name
- Status pill (Active / Draft / Archived)
- Updated timestamp
- Optional secondary metadata (activated at, last used) if available

Row actions:

- Draft:
  - Primary: **Make active**
  - Secondary (overflow menu): Open editor, Run validation, Export, Duplicate, Rename (draft-only, optional)
- Active:
  - Primary: **Duplicate to edit**
  - Secondary (overflow menu): Open editor, Export, Archive (danger)
- Archived:
  - Primary: **Duplicate to edit**
  - Secondary (overflow menu): Open editor, Export

Small UX details (to keep the screen intuitive at scale):

- Sorting: show **Active** first, then Drafts by most recently updated, then Archived (collapsed by default when list is long).
- Action hierarchy: show one primary button per row; put “Export”, “Run validation”, and other utilities in `…` to reduce clutter.
- Consistent verbs: prefer “Open editor” everywhere; the editor surface enforces read-only vs editable mode based on status.
- Make it scannable: show section counts (e.g., “Drafts (3)”), and keep the Active card visually distinct.
- Active card content: add a short subtitle like “Used for extraction runs” and a small “Last activated …” line if available.
- Search: add a lightweight name filter (client-side) once the list can grow (do not add if it creates clutter).
- Click targets: make the row/card click open **Details**, while keeping buttons explicit (avoid accidental activation).
- IDs: show a short ID with a copy-to-clipboard affordance (full ID available on hover/tooltip).
- Empty states:
  - No configs → “Create your first configuration” (existing state).
  - No Active config → show a prominent warning card with a single CTA: “Make a draft active”.
  - No Drafts → show a small helper hint (“Duplicate Active to start editing”).
- Timestamp formatting: relative (“Updated 3 hours ago”) with a hover tooltip for the exact time.
- Status chips: consistent colors + iconography (Draft = amber, Active = green, Archived = slate).
- Status tooltips: explain meaning (“Active is used for runs”, “Draft is editable”, “Archived is read-only history”).
- Permissions: hide lifecycle actions if the user lacks `workspace.configurations.manage` (show read-only labels instead).

### 4.3 Configuration detail UX

Detail page becomes the “source of truth” for lifecycle actions and guardrails:

- Header: name + status pill + quick actions (contextual, not always shown):
  - Draft: **Make active** (primary), Duplicate (secondary), Export (overflow)
  - Active: **Duplicate to edit** (primary), Export (overflow), Archive (danger zone)
  - Archived: **Duplicate to edit** (primary), Export (overflow)
- Metadata panel: id, status, updated, activated at, last used, content digest (if available)
- Small quality-of-life: include a “Copy ID” button and format timestamps consistently (relative + exact tooltip).
- Read-only callout when not draft:
  - “This configuration is locked. Duplicate it to make changes.”
  - Button: **Duplicate to edit**

### 4.4 Workbench/editor UX

Workbench must be explicit about editability:

- Draft:
  - Full editor enabled; show “Draft” pill.
  - Add a prominent **Make active** button near existing actions (export/import menu).
- Active/Archived:
  - Editor is read-only (disable save, edits, file create/rename/delete).
  - Banner at top:
    - Title: “Read-only configuration”
    - Body: “Active/Archived configs can’t be edited. Duplicate to create a draft you can change.”
    - CTA: **Duplicate to edit**

Workbench polish details:

- Disable (don’t hide) editing controls with a short tooltip explaining why they’re disabled.
- Use a single, consistent CTA location for “Duplicate to edit” (banner + overflow menu), so users don’t have to hunt.
- If a user navigates directly to `/editor` for a non-draft config, keep the route but force read-only mode (don’t 404).
- When duplicating from within the workbench, auto-open the new draft in the editor and preserve the “return path” back to the configuration list.
- If there are unsaved editor changes, disable “Make active” and guide the user to **Save all** first (or offer a “Save & make active” flow).
- After “Make active” succeeds from inside the workbench, immediately switch the session to **read-only** and surface a success banner:
  - “Configuration is now active and locked. Duplicate to make further edits.”
- Read-only affordances: add a subtle lock icon + “Read-only” pill in the editor header (not just a banner) to keep users oriented while scrolling.

### 4.5 Confirmation + failure modes

Make active confirmation (Draft → Active):

Preferred interaction pattern: one modal with a quick preflight.

- Step 1 (auto): “Checking configuration…” (runs validation; show spinner, allow cancel)
- Step 2A (ok): show confirmation
  - Title: “Make configuration active?”
  - Body:
    - “This becomes the workspace’s live configuration for extraction runs.”
    - “The current active configuration <name> will be archived.”
  - Primary button: “Make active”
  - Secondary button: “Cancel”
- Step 2B (issues): block activation and show issues
  - Title: “Fix validation issues first”
  - Body: short summary + expandable list of issues with file paths
  - Primary button: “Open editor”
  - Secondary button: “Close”

Archive confirmation (Active → Archived):

- Title: “Archive active configuration?”
- Body:
  - “This will leave the workspace with no active configuration.”
  - “Extraction runs will be blocked until you make a draft active.”
- Place “Archive” behind progressive disclosure (overflow menu or danger zone); most users switch configs via “Make active”, which archives automatically.
- Visual treatment: destructive button styling and wording (“Archive”) consistent with other danger actions in the app.

Duplicate flow:

- Modal asks for a new name (default: “Copy of {name}”).
- Auto-suggest a unique name (e.g., append “(Copy)” or “v2” if needed) to avoid server-side collisions.
- Creates a new draft via clone.
- Preserve user input on failure (e.g., name conflict or network error) and show the error inline in the modal.
- On success: navigate directly into the editor for the new draft.
- Success feedback: toast “Draft created” with a subtle “View details” link (optional).

### 4.6 API + data model alignment (recommended)

To match DD-0002 and simplify UX, standardize status values to exactly:

- `draft`
- `active`
- `archived`

Recommended backend changes:

- Replace `inactive` → `archived` (wire + DB value).
- Remove or deprecate `published`; migrate existing `published` rows to `archived`.
- Align lifecycle endpoints/semantics:
  - `POST …/{id}/publish`: Draft → Active (and archive previous active in the same transaction).
    - UI label should be “Make active” even if the endpoint remains `/publish`.
  - Keep `POST …/{id}/activate` as an alias (or deprecate in docs) for backwards compatibility.
  - `POST …/{id}/archive` (alias existing `/deactivate`): Active → Archived.
- Enforce single active per workspace in DB:
  - Partial unique index: `UNIQUE(workspace_id) WHERE status='active'` (Postgres).
  - On conflict, return a 409 with a clear problem code so the UI can retry/refetch.

If API/status changes are too risky right now:

- Keep current wire values but map them in the UI:
  - `inactive|published` → Archived
  - Hide “published” entirely from UX
  - Implement the UX flows using existing endpoints.

### 4.7 Documents run flow (active default)

Update Documents “Run extraction” drawer:

- Default to the workspace’s **Active** config and reduce choices:
  - Show a compact label (“Using: <active config name>”) with a “Change” affordance.
  - In “Change”, show only Active by default; allow Draft selection under an “Advanced” toggle if desired.
- If no active config:
  - Show a blocking message: “No active configuration. Make a draft active to run extraction.”
  - Provide a shortcut link/button to Configuration Builder.
- Optionally allow selecting a Draft for test runs behind an “Advanced” toggle.

---

## 5. Open questions / decisions

1) **Verb:** In the UI, do we label the promote action “Publish”, “Activate”, or “Make active”?
   - Recommendation: **Make active** (most explicit; avoids confusion with a separate “Published” state).
2) **No-active state:** Is it allowed for a workspace to have **zero** active configurations?
   - Recommendation: **Yes** (supports deliberate retirement), but block Documents runs until one is made active.
3) **Published status:** Do we keep a separate “Published (frozen, not active)” state?
   - Recommendation: **No** for now; it complicates UX and does not match DD-0002.
4) **Re-activating archived configs:** Should archived configs be directly activatable?
   - Recommendation: **No** (preserves audit trail; rollback is duplicate → make active).

---

## 6. Implementation & notes for agents

### 6.1 Expected code touch points

Backend (if we do API/status alignment):

```text
apps/ade-api/src/ade_api/models/configuration.py
apps/ade-api/src/ade_api/features/configs/service.py
apps/ade-api/src/ade_api/features/configs/endpoints/configurations.py
apps/ade-api/migrations/versions/*  # status rename + partial unique index
```

Frontend:

```text
apps/ade-web/src/shared/configurations/api.ts
apps/ade-web/src/shared/configurations/hooks/useConfigurationLifecycle.ts
apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/index.tsx
apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/detail/index.tsx
apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx
apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx
```

### 6.2 Validation / commands

- Backend + frontend tests: `ade tests`
- Full pipeline (before PR): `ade ci`
- After API shape changes: `ade types` (regenerates `apps/ade-web/src/generated-types/openapi.d.ts`)

### 6.3 Acceptance criteria

- A workspace clearly indicates the **Active** configuration.
- Users can **Make active** a draft, which becomes active and automatically archives the previous active config.
- Users can **Archive** the active config (if allowed) and the app responds appropriately (documents runs blocked until a draft is made active).
- Users can **Duplicate** any config into a draft and edit it; “rollback” is naturally supported by this flow.
- Active/Archived configs are **read-only** everywhere; the workbench explicitly guides users to duplicate instead of failing saves.
