---
Audience: Platform administrators
Goal: Run ADE locally on Windows with PowerShell for fast iteration without Docker.
Prerequisites: Windows 10/11 with PowerShell 5+, Python 3.11+, Node.js 20+, Git, and internet access to install dependencies.
When to use: Follow this guide when you need a laptop-friendly ADE environment for development, demos, or configuration validation.
Validation: `GET /health` returns `{ "status": "ok" }`, the Vite dev server renders the sign-in screen, and `pytest -q` passes.
Escalate to: Platform owner or DevOps lead if dependencies fail to install, services refuse to start, or validation steps do not pass.
---

# Local quickstart (Windows PowerShell)

This walkthrough keeps the setup simple: every instruction explains why it matters and then immediately shows the PowerShell commands to run. Complete the steps in order from the project root.

## Before you start

Confirm the required tools are available. Run the commands below and verify each version meets or exceeds the minimum.

| Tool | Minimum version | Check command |
| --- | --- | --- |
| Python | 3.11 | `python --version` |
| Node.js | 20 | `node --version` |
| npm | Bundled with Node.js | `npm --version` |
| Git | Latest LTS | `git --version` |

```powershell
python --version
node --version
npm --version
git --version
```

If any command is missing, install the tool before continuing.

## Step 1: Create an isolated Python environment

Use a virtual environment so backend dependencies stay contained inside the repository.

```powershell
# From the project root
Set-Location C:\path\to\automatic-data-extractor

# Create and activate the virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies (including dev tools)
pip install -e ".[dev]"
```

You should see the `.venv` prefix in your prompt after activation. If PowerShell blocks the activation script, allow it for the current session and rerun the previous command.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Step 2: Start the backend with auto-reload

Launch the FastAPI application so the API and SQLite database come online.

```powershell
python -m uvicorn backend.app.main:app --reload
# Server starts at http://127.0.0.1:8000
```

Validate the API in a new PowerShell tab while the server keeps running.

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health | Select-Object -ExpandProperty Content
```

You should receive `{ "status": "ok" }`. If the command fails, verify that the previous window still shows the Uvicorn server running and no errors appear in its logs. Escalate if dependency installation repeatedly fails.

## Step 3: Install frontend packages and start Vite

Open another PowerShell window, keep the backend running, and start the React frontend.

```powershell
# From the project root
Set-Location C:\path\to\automatic-data-extractor
cd frontend

npm install
npm run dev
# Vite starts at http://127.0.0.1:5173 and proxies API calls to http://127.0.0.1:8000
```

Visit `http://127.0.0.1:5173` in a browser. You should see the ADE sign-in screen. If the page fails to load, confirm the backend is still available and that no firewall is blocking port **5173**.

## Step 4: Run the quick test suite

Before making changes, run the backend tests in the environment you just configured.

```powershell
# From the project root with the virtual environment active
pytest -q
```

Front-end linting and type checks remain available when needed.

```powershell
npm run lint
npm run typecheck
```

## Troubleshooting quick fixes

- **`uvicorn` command not found:** run `python -m uvicorn backend.app.main:app --reload` (already shown above) to use the interpreter that owns the dependency.
- **Port 8000 or 5173 in use:** choose an open port and pass `--port <number>` to the `uvicorn` command, or set `--port` inside `npm run dev` (`npm run dev -- --port 5174`).
- **Stuck virtual environment:** close PowerShell windows and delete `.venv` before recreating it with `python -m venv .venv`.
- **Need Docker later:** finish this quickstart first, then consult platform deployment guides once container documentation lands.

When everything works, continue with [environment and secret management](./environment-management.md) to persist your settings across sessions.
