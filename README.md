# Automatic Data Extractor
> _One‑sentence value prop: **what it does**, **for whom**, and **why it’s better**._  

[![Build Status](#)](#) [![License](#)](#) [![Coverage](#)](#)

## Quick links
- [Overview](#overview) • [Quick start](#quick-start) • [Project structure](#project-structure) • [Commands](#commands) • [Configuration](#configuration) • [API](#api) • [Deploy](#deploy) • [Contributing](#contributing)

---

## Overview
**What is this?**  
_Add a 2–3 sentence overview of the product. Mention the core problem, the outcome, and the primary user._

**Why it matters**  
_Briefly list 3–4 headline benefits (speed, reliability, accuracy, cost)._

**Screenshot / demo (optional)**  
_Add a short GIF or image here._

**Tech stack**  
FastAPI • Python 3.11 • React Router • TypeScript • Vite • Node.js 20

---

## Quick start
Prereqs: **Node 20+**, **Python 3.11+**, _Git optional_.  
```bash
# 1) Get the code
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor

# 2) One-time setup (installs Node deps + creates backend venv)
npm run setup

# 3) Configure (copy then edit if needed)
cp backend/.env.example backend/.env

# 4) Run dev servers (API + Web)
npm run dev
# API:     http://localhost:8000
# Frontend http://localhost:5173
````

---

## Project structure

```
automatic-data-extractor/
├─ backend/        # FastAPI app with feature-first modules + tests
├─ frontend/       # React Router app (TypeScript, Vite)
├─ scripts/        # Shared Node helpers for monorepo workflows
└─ package.json    # Unified scripts (setup, dev, build, ci, etc.)
```

Key backend directories:

```
backend/app/
├─ main.py            # FastAPI factory + middleware
├─ api/v1/__init__.py # Composes routers from feature packages
├─ features/          # Vertical slices (auth, users, documents, jobs, workspaces, health)
│  └─ <feature>/
│     ├─ router.py    # FastAPI router for the feature
│     ├─ schemas.py   # Pydantic models for the feature
│     ├─ service.py   # Business logic for the feature
│     └─ repository.py # Persistence logic (if applicable)
├─ shared/            # Cross-cutting helpers (config, logging, security, db, repository base)
└─ web/static/.gitkeep # Placeholder for built SPA assets
```

---

## Commands

Use the standard npm scripts (`npm run <script>`). There’s also an `ade` alias if you prefer shorter commands—run `ade` to list the available scripts.

```bash
# Dev
npm run dev          # FastAPI (reload) + Vite dev server

# Introspection
npm run routes       # Print API + frontend routes as JSON

# Quality
npm run test         # Backend pytest + frontend checks
npm run ci           # Setup → tests → build → routes

# Build & serve
npm run build        # Compile SPA into backend/app/web/static
npm run start        # Serve FastAPI + static frontend

# Types
npm run openapi-typescript   # Regenerate frontend/app/types/api.d.ts

# Maintenance
npm run clean:force  # Remove build artifacts + deps
npm run reset:force  # Clean workspace and re-run setup
```

---

## Configuration

Place overrides in `backend/.env` (see `backend/.env.example`).
*Note anything the app requires (e.g., `DATABASE_URL`, API keys). Don’t commit secrets.*

---

## API

* Docs: **`/docs` (Swagger UI)** and **`/redoc`** when the API is running.
* OpenAPI types: `npm run openapi-typescript` updates `frontend/app/types/api.d.ts`.

---

## Deploy

**Production (simple):**

```bash
npm run build                   # build SPA → backend/app/web/static
npm run start
# FastAPI listens on http://0.0.0.0:8000 (add a reverse proxy for TLS/host routing)
```

**Docker (optional):**

```bash
docker build -t automatic-data-extractor .
docker run --rm -p 8000:8000
```

---

## Roadmap (optional)

*Bulleted list of near-term milestones or a link to your tracker.*

---
