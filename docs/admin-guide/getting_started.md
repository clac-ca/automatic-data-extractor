# ADE Admin Getting Started Guide

This handbook shows how to run and administer the Automatic Data Extractor (ADE)
without assuming prior context. ADE is designed to be a small, self-contained
service that relies on a bundled SQLite database, so you can evaluate it
anywhere without provisioning external infrastructure.

## 1. What ADE Ships With
- **Self-contained storage** – ADE persists all metadata in
  `backend/data/db/ade.sqlite`. Documents and other artefacts live alongside it
  under `backend/data/`. No external database service is required.
- **Deterministic FastAPI backend** – requests are handled by the app in
  `backend/api/main.py`. Background work stays inside the same process.
- **Admin CLI** – the `ade` command lets you manage users and API keys from any
  terminal that can read the project’s environment.
- **(TODO)** The forthcoming frontend will guide first-time administrators
  through setup. Until it lands, use the CLI steps below.

## 2. About `.env` Files
ADE reads configuration from environment variables. During local development we
keep them in a `.env` file in the project root so FastAPI, the CLI, and Docker
all load the same values.

An example file is included. Copy it and adjust the values you need:

```bash
cp .env.example .env
# edit .env to set secrets before starting ADE
```

If you delete `.env`, ADE falls back to its defaults (SQLite in
`backend/data/db`, docs disabled outside `local`, etc.).

## 3. Option A – Run ADE Directly with Python
Requirements: Python 3.11, `git`, and build essentials for your OS.

```bash
git clone https://github.com/your-org/automatic-data-extractor.git
cd automatic-data-extractor
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev]
uvicorn backend.api.main:app --reload
```

Verify the API is up and serving requests:

```bash
curl http://127.0.0.1:8000/health
```

All runtime state stays under `backend/data/`. Remove that directory to reset
ADE to a clean slate (for example, between demos).

## 4. Option B – Run ADE with Docker
Docker is useful when you want ADE isolated from the host Python install or to
run it on a server. An official image will be published to GitHub Container
Registry soon.

> **TODO:** Replace the build step below with a `docker pull` command once the
> image is published.

### 4.1 Build a local image
```bash
git clone https://github.com/your-org/automatic-data-extractor.git
cd automatic-data-extractor
cp .env.example .env
docker build -t ade-backend:local -f docker/backend/Dockerfile .
```

### 4.2 Run the container
```bash
docker run -d --name ade-backend \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/backend/data:/app/backend/data" \
  ade-backend:local \
  uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

The bind mount keeps the SQLite database and documents on the host so they
survive container restarts. Check health the same way:

```bash
curl http://127.0.0.1:8000/health
```

To stop and remove the container:

```bash
docker stop ade-backend
docker rm ade-backend
```

## 5. Managing ADE with the CLI
The CLI uses the same settings as the API. It works even when the API is not
running, as long as the `.env` file (or equivalent environment variables) is
accessible.

From a virtual environment or any Python install where ADE is installed:

```bash
# Create the first administrator account
ade users create --email admin@example.com --password "TempPass123!" --role admin

# List existing users (JSON output is handy for scripts)
ade users list --json

# Reset a password without touching the database manually
ade users set-password --email admin@example.com --password-file ~/.secrets/new-password.txt

# Issue and revoke API keys for service automation
ade api-keys issue --email service@example.com --expires-in 30 --json
ade api-keys revoke 01KZYXWVUTSRQPONML
```

When ADE runs in Docker, execute the same commands inside the container so they
share configuration:

```bash
docker exec -it ade-backend ade users create --email admin@example.com --password "TempPass123!" --role admin
```

> **Tip:** Because the CLI talks directly to the SQLite database, avoid running
> long CLI operations while ADE is actively processing heavy requests to keep
> contention low.

## 6. Where ADE Stores Data
- `backend/data/db/ade.sqlite` – primary metadata database (SQLite).
- `backend/data/documents/` – uploaded source files.
- `backend/data/logs/` *(if enabled)* – structured JSON logs.

Back up the `backend/data/` directory to retain everything you need for a full
restore.

## 7. Roadmap + TODOs
- **TODO:** Publish an official Docker image to GitHub Container Registry and
  reference it in this guide.
- **TODO:** Update the onboarding section once the frontend ships the admin
  walkthrough.
- Consider setting `ADE_AUTH_TOKEN_SECRET` to a long random value before going
  beyond local testing.

With these basics you can run ADE on a laptop, VM, or container host and manage
administrators confidently using the CLI.
