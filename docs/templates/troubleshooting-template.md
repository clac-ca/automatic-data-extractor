# Troubleshooting Guide Template

Introduction: Scope of this troubleshooting guide and how to use it.

## How to use this guide

Start with logs and a minimal reproduction. Confirm version and environment.

---

## Common issues and solutions

1. Validation error on startup

Symptom: “Invalid configuration: unknown field …”.

Cause: Typo or wrong field in a config file.

Fix:

- Compare against the schema reference.
- Correct field names and types.
- Re‑run validation/tests:

```bash
pytest -q
```

2. API not responding

Symptom: Requests to the local API hang or fail.

Possible causes: Service not started, migrations not applied, or dependency down.

Fix:

- Start services:

```bash
ade dev
```

- Apply migrations:

```bash
alembic upgrade head
```

- Check health:

```bash
curl -s http://localhost:8000/api/health
```

3. Permission denied

Symptom: Errors indicating file or port permissions.

Fix: Adjust file permissions, avoid privileged ports, verify container volume ownership.

---

## Getting more help

- Check related docs or FAQ
- Open a discussion with logs and reproduction steps

