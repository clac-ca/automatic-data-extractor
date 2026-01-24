# How‑to Guide Template

Title: <How to accomplish X> (Title Case)

Description: A one‑line summary of this how‑to guide.

---

## Introduction

State what this guide helps the reader do and any assumptions. Keep it short.

Prerequisites (optional):

- Dependencies installed (run `uv sync --locked` and `source .venv/bin/activate`)
- Access to a local API (`ade dev`)

---

## Steps

1. Step 1 — Describe the action precisely. For example, enable a feature:

   ```bash
   curl -X POST http://localhost:8000/api/v1/features/enable -d '{"name":"logging"}' -H 'Content-Type: application/json'
   ```

   Expected result: the API returns `{"ok": true}`.

2. Step 2 — Edit configuration or run a script:

   ```bash
   alembic upgrade head
   ```

3. Step 3 — Verify with tests:

   ```bash
   pytest -q
   ```

> Tip: Keep steps focused and minimal. If you need >7 steps, consider a tutorial instead.

---

## Conclusion

Summarize the outcome and call out any next actions.

## Related

- Reference: <Link to API or schema>
- Troubleshooting: <Link to common issues>
