# API Reference Template

Overview: Brief description of the API (or section) covered.

Base URL

- Base: `http://localhost:8000/api`
- Auth: <Describe (for example, API key in `Authorization` header)>
- Content type: `application/json`

---

## GET /health — Health check

Description: Returns service health.

Example request:

```bash
curl -s http://localhost:8000/api/health
```

Example response:

```json
{ "status": "ok" }
```

Errors:

- 500 Internal Server Error — Service unhealthy

---

## POST /jobs — Create a job

Description: Creates a new job.

Request body:

```json
{
  "name": "example",
  "priority": 5
}
```

Example request:

```bash
curl -s -X POST http://localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"name":"example","priority":5}'
```

Example response:

```json
{ "id": "job_123", "name": "example", "status": "queued" }
```

Errors:

- 400 Bad Request — Invalid payload
- 401 Unauthorized — Missing or invalid credentials

---

## Data model

Job object:

- `id` (string) — Identifier
- `name` (string) — Human‑readable name
- `status` (string) — Current state (for example, `queued`, `running`, `done`)
- `createdAt` (string, ISO 8601) — Creation timestamp

