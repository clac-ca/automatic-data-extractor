# AGENTS.md
## 🧱 Project Overview

```
repo/
├─ apps/api/app/  # FastAPI backend on port 8000 (serves /api/*)
├─ apps/web/     # React Router dev server on port 8000 (file-based routes)
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
npm run build   # Build SPA → apps/api/app/web/static
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
