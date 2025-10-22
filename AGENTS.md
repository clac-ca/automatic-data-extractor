# AGENTS.md
## 🧱 Project Overview

```
repo/
├─ backend/app/  # FastAPI backend on port 8000 (serves /api/*)
├─ frontend/     # React Router on port 5173 (file-based routes)
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
npm run routes  # Show routes JSON
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
6. Optional: check routes → `npm run routes`.
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

**End of AGENTS.md**
