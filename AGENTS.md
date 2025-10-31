# AGENTS.md
## 🧱 Project Overview

```
repo/
├─ backend/app/  # FastAPI backend on port 8000 (serves /api/*)
├─ frontend/     # React Router dev server on port 8000 (file-based routes)
├─ scripts/      # Node helpers for automation
├─ package.json  # Root command center
└─ README.md
```

---

## ⚡ Available Tools

You may use `ade <script>` as a shortcut for any `npm run <script>` command; both forms stay in sync.

```bash
npm run setup   # Install deps
npm run dev     # FastAPI + React Router
npm run test    # Run all tests
npm run build   # Build SPA → backend/app/web/static
npm run start   # Serve API + SPA
npm run openapi-typescript # Export backend schema + generate TS types
npm run routes:frontend  # List frontend (React Router) routes as JSON
npm run routes:backend   # Summarize backend FastAPI API routes
npm run workpackage # Manage work packages (JSON CLI)
npm run clean:force  # Remove build/installs without confirmation
npm run reset:force  # Clean + setup without confirmation
npm run ci      # Full CI pipeline
```

---

## 🧩 Standard Workflows

### Add or Change Code

1. Create branch → `feat/<scope>` or `fix/<scope>`.
2. Run `npm run dev`.
3. Edit:

   * Backend → `backend/app/...`
   * Frontend → `frontend/src/app/routes/...`
4. Run `npm run test`.
5. Build & verify → `npm run build && npm run start`.
6. Optional: check frontend routes → `npm run routes:frontend`.
7. Regenerate API types if backend surfaces change → `npm run openapi-typescript`.
8. Commit → `feat(api): add /api/v1/hello`.
9. Open PR → `main`.

### Work Packages (Agents + Humans)

**Kickoff**
- Check for in-flight efforts: `npm run workpackage list -- --active`.
- If the work you plan overlaps an active package, do not create a new one—coordinate via `npm run workpackage note <ref>` or pass ownership instead.
- Claim the package you’re touching: `npm run workpackage status <ref> -- --to active`.
- Drop a quick note on intent: `npm run workpackage note <ref> -- --text "starting XYZ"`.

**Avoid collisions**
- Before touching files, confirm no other active package owns them; if there is overlap, pause and sync with the active owner instead of editing.
- When in doubt, leave a note and wait for confirmation before proceeding—better to idle than risk clobbering work in progress.
- If you only need visibility, use `npm run workpackage show <ref>` and stay read-only until you coordinate a handoff.

**During**
- Log meaningful progress with `npm run workpackage note <ref> -- --text "update"`.
- Use `npm run workpackage show <ref>` for the full context blob (notes, paths, metadata).

**Wrap-up**
- Leave a summary note capturing what changed.
- Park the package: `npm run workpackage status <ref> -- --to done` (or `blocked`/`draft` as needed).

**Other commands**
- Create new package: `npm run workpackage create -- --title "<title>" --summary "<goal>"`.
- Check for overlaps up front: `npm run workpackage list -- --status active,blocked`.
- Search titles/notes: `npm run workpackage find "<text>"`.
- Stream recent events: `npm run workpackage tail <ref>`.
- Snapshot the board: `npm run workpackage board`.
- Delete a single package: `npm run workpackage delete <ref> -- --yes` (explicit confirmation keeps accidents at bay).
- Listings include a short description from summaries for quick scanning.
- Every package lives in `.workpackage/packages/<id>-<slug>/` with `workpackage.json`, `notes.md`, `log.ndjson`, and an `attachments/` folder for supporting docs or plans.
- Need to wipe everything? Run `npm run workpackage clear` and type `yes` when prompted (no force flag by design).

### Debug a Failing Build

1. Run `npm run ci`.
2. Read JSON output (stdout).
3. Fix first error.
4. Re-run until `"ok": true`.

---

## 🔧 TODO IN FUTURE WHEN POSSIBLE

* Add linting/formatting: `ruff`/`black` (Python), `eslint`/`prettier` (JS).

---

## 🤖 Agent Rules

1. Always run `npm run test` before committing and `npm run ci` before pushing or opening a PR.

---

## 📚 Developer Docs

- Read and follow `docs/developers/AGENTS.md` before adding or updating developer documentation.
- Structure lives under `docs/developers/`:
  - `templates/` — page and snippet templates (use these).
  - `schemas/` — JSON Schemas referenced from docs.
  - `design-decisions/` — Design Decisions (DD).
  - Numbered pages (e.g., `01-config-packages.md`, `04-pass-map-columns-to-target-fields.md`). Keep numbers stable.

When to update docs (triggers)

- API surface changes (routes, params, response shapes)
  - Record the change under `13-design-decisions.md` and link the relevant DD.
- Manifest or mapping schema shape changes
  - Update: `docs/developers/schemas/*`, `04-pass-map-columns-to-target-fields.md`, and `01-config-packages.md` if contracts changed.
- Script contracts (hooks/detectors/transforms) or kwargs change
  - Update: `01-config-packages.md` and `05-pass-transform-values.md`.
- Pipeline behavior or pass boundaries change
  - Update: `02-job-orchestration.md`; consider a DD (see below).
- Validation or diagnostics shape change
  - Update: `06-pass-validate-values.md`.
- Security/secrets behavior change
  - Record updates in `13-design-decisions.md`; add or revise a DD as needed.
- New common authoring pattern or best practice
  - Update: `10-examples-and-recipes.md` (add a small copy‑pasteable example).

Navigation conventions

- Each page ends with “Next” and “Previous” relative links.
- First use of a defined term links to `docs/developers/12-glossary.md`.

---

## 📌 Design Decisions (DD)

Use a DD when the change is:

- Cross‑cutting or repo‑level (affects multiple components or workflows), or
- Establishes a long‑lived invariant or security stance, or
- Defines an external contract or versioned data shape, or
- Introduces a new execution model or lifecycle step, or
- Trades off performance/complexity with lasting impact.

Do not create a DD for:

- Local refactors, implementation details, or temporary experiments.

Where and how

- Location: `docs/developers/design-decisions/`.
- Naming: `dd-####-slug.md` (zero‑padded; next available number; do not renumber).
- Format: Date → Context → Decision → Consequences → Alternatives considered → Links.
- Superseding: add “Supersedes: dd‑####” or “Superseded by: dd‑####” in both files.

Link DDs from relevant pages (overview, runtime, mapping, security) so readers see the “why,” not just the “what.”

---

**End of AGENTS.md**
