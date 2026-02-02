# Automatic Data Extractor (ADE)

Self-hostable document extraction service with an **API**, **Web UI**, and background **worker**.

- Local dev: runs with **Docker Compose** (includes local Postgres + Azurite).
- Production: uses **external Postgres** + **external Azure Blob Storage**.

---

## Table of contents

- [Quickstart (local)](#quickstart-local)
- [Production deployment](#production-deployment)
- [Configuration](#configuration)
- [Development (Dev Container)](#development-dev-container)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)
- [Docs](#docs)

---

## Quickstart (local)

### Requirements
- Docker (with Docker Compose)
- Git

### Run

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor
docker compose up --build -d postgres azurite azurite-init
docker compose run --rm api ade db migrate
docker compose up -d api worker web
````

Open:

* [http://localhost:8000](http://localhost:8000)

Stop:

```bash
docker compose down
```

Reset local data (database + storage + ADE data):

```bash
docker compose down -v
```

---

## Production deployment

Production uses:

* **External Postgres**
* **External Azure Blob Storage**

ADE runs as **split services** (separate containers) using the same image:

```bash
docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml up -d
```

---

## Configuration

Create a `.env` file **next to the compose file you run**.

### Minimum required (example)

```env
# Database (external)
ADE_DATABASE_URL=postgresql+psycopg://user:pass@pg.example.com:5432/ade?sslmode=verify-full

# Azure Blob (choose ONE auth method supported by your deployment)
ADE_BLOB_ACCOUNT_URL=https://<account>.blob.core.windows.net
ADE_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net

ADE_BLOB_CONTAINER=ade

# App secret (required)
ADE_SECRET_KEY=<long-random-secret>
```

See `.env.example` for the full set of supported environment variables.

### Service selection (optional)

To start only a subset of services:

```bash
docker compose up -d api web
```

---

## Development (Dev Container)

Fastest contributor setup:

1. Install Docker + VS Code + Dev Containers extension
2. Open the repo in VS Code
3. Run **“Dev Containers: Reopen in Container”**

---

## Operations

### View logs

```bash
docker compose logs -f
```

### Start fresh

```bash
docker compose down -v
```

---

## Troubleshooting

* Check logs:

  * `docker compose logs -f`
* Full reset:

  * `docker compose down -v`

---

## Docs

Full documentation lives in `docs/index.md`.

## Contributing

PRs welcome. If you’re making a change, please include:

* What changed
* How to run/test it locally

---

## Security

* Treat `ADE_SECRET_KEY` like a password.
* For production, run behind HTTPS and restrict network access to Postgres/Blob where possible.

---

## License
 
The MIT License (MIT)

Copyright (c) 2015 Chris Kibble

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
