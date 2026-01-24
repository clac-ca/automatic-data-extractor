# Tutorial Template

Title: <Tutorial Title (Title Case)>

Audience: <who should follow this tutorial>

Goal: <what they will build or do>

> At a glance
>
> - One‑line description of the outcome.
> - 3–5 bullets for the main steps.

Prerequisites: <installed software, accounts, sample files, prior tutorials>

---

## Introduction

State the goal in a couple of sentences—what the reader will build or learn. Keep it short and motivating.

## Step 1: <First major step title>

Explain the step’s purpose and provide clear, numbered sub‑steps:

1. Action — Describe the action to take. For example, install deps and start dev services:

   ```bash
   uv sync --locked  # create .venv, install packages
   source .venv/bin/activate
   ade dev           # starts API + web + worker in watch mode
   ```

2. Next action — For example, run backend migrations and tests:

   ```bash
   alembic upgrade head
   pytest -q
   ```

3. Verification — Call a health endpoint locally:

   ```bash
   curl -s http://localhost:8000/api/v1/health
   ```

> Tip: Add notes or warnings for common pitfalls, but keep them brief.

## Step 2: <Next major task>

Introduce what this step covers and provide instructions, code blocks, or UI actions. Keep each step focused on a single outcome. If more than ~5 sub‑steps are needed, consider splitting the step.

### Example snippet

```python
@app.route("/hello")
def hello():
    return "Hello, world!"
```

## Step 3: <Next step>

Repeat the pattern as needed for the tutorial’s flow (for example, Test, Deploy, Validate).

## Minimal example (optional)

Show the smallest working snippet relevant to the tutorial (≤ 30 lines). Use realistic placeholders and follow `./snippet-conventions.md`.

```python
print("hello tutorial")
```

## Summary

Summarize what the reader accomplished and learned.

## What’s next

- Next: <Link to an advanced tutorial>
- Reference: <Link to API/Config reference>
- Troubleshooting: <Link to a common-issues page>
