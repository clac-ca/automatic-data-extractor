# AGENTS.md
## 🧱 Project Overview

```
repo/
├─ backend/      # FastAPI backend on port 8000 (serves /api/*)
├─ frontend/     # React Router on port 5173 (file-based routes)
├─ scripts/      # Node helpers for automation
├─ package.json  # Root command center
└─ README.md
```

---

## ⚡ Available Tools

```bash
npm run setup   # Install deps
npm run dev     # FastAPI + React Router
npm run test    # Run all tests
npm run build   # Build SPA → backend/static
npm run start   # Serve API + SPA
npm run openapi-typescript # Export backend schema + generate TS types
npm run routes  # Show routes JSON
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
   * Frontend → `frontend/app/routes/...`
4. Run `npm run test`.
5. Build & verify → `npm run build && npm run start`.
6. Optional: check routes → `npm run routes`.
7. Regenerate API types if backend surfaces change → `npm run openapi-typescript`.
8. Commit → `feat(api): add /api/v1/hello`.
9. Open PR → `main`.

### Debug a Failing Build

1. Run `npm run ci`.
2. Read JSON output (stdout).
3. Fix first error.
4. Re-run until `"ok": true`.

---

## 🔧 TODO IN FUTURE WHEN POSSIBLE

* Add linting/formatting: `ruff`/`black` (Python), `eslint`/`prettier` (JS).
* Add a single Dockerfile to serve API + SPA.

---

## 🤖 Agent Rules

1. Always run `npm run test` before committing and `npm run ci` before pushing or opening a PR.

---

**End of AGENTS.md**
