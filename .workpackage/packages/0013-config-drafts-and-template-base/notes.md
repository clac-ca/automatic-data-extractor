# Config drafts & base template

Owner: unknown  
Status: active  
Created: 2025-11-03T19:45:00Z

---

## Goal
Allow users to create configuration drafts on demand using a single **default template**.  
This replaces auto-seeding and sets the foundation for a future template catalog.

---

## Behavior

### 1. Draft creation
- Users create drafts manually from the Config screen or when a job is attempted with no active config.  
- Options:  
  - **From Default Template** — prepopulated manifest with standard engine defaults.  
  - **Import ZIP** — upload existing config package (manifest + hooks + columns).  
- The result is always a **draft**, not active.

### 2. Activation
- Activation re-validates the draft, runs `on_activate` hooks, and marks it active for the workspace.  
- Only one active version exists at a time; the previous one is archived.

### 3. Default template
- Stored under `backend/app/features/configs/templates/default/`.  


### 4. Import safety
- Validate ZIP content:
  - Allowed paths: `manifest.json`, `columns/*.py`, `hooks/*.py`, `row_types/*.py`, `requirements.txt`.
  - No symlinks, binaries, or hidden files.  
- Always results in a **draft**.

### 5. Future templates
- Add new templates by placing folders under `templates/` with `template.json` metadata.  
- Default template acts as fallback if no others are defined.

---

## API behavior
- `POST /configs/drafts`  
  - `mode: "template" | "import"`  
  - Returns created draft + diagnostics.
- `POST /configs/{version_id}/activate`  
  - Re-validate + run hooks + activate.
- Jobs without active config → 400 `{ code: "no_active_config" }`.

---

## Acceptance
- [ ] Drafts can be created from the default template or import ZIP.  
- [ ] Activation works and records annotations.  
- [ ] No auto-created configs on workspace creation.  
- [ ] Default template loads correctly from disk.  
- [ ] Import ZIP validates structure and rejects unsafe files.

---

## Future
- Add multiple templates via `templates/` catalog.  
- Add optional sample file inference for columns.
