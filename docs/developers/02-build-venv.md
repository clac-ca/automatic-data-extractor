# 02 — Environment Venvs (Worker-Owned)

This document describes how ADE provisions and caches execution environments.
Build orchestration has been removed from the API; environments are created by
the worker as runs start.

---

## What an environment is

An **environment** is a Python virtualenv that contains:

* `ade_engine`
* the configuration package (`ade_config`)

Environments are keyed by:

* `workspace_id`
* `configuration_id`
* `engine_spec`
* `deps_digest`

Environments are **not** user jobs. The worker provisions them as needed and
marks them `ready` for reuse.

---

## Storage layout

```
./data/venvs/<workspace_id>/<configuration_id>/<deps_digest>/<environment_id>/.venv
```

Override the base with `ADE_VENVS_DIR` if needed.

---

## Dependency digests

`deps_digest` is computed from dependency manifests only (for example
`pyproject.toml`, `requirements.txt`). Source edits (`.py`) do **not** change
the digest when configs are installed editable, so environments are reused
across code edits.

---

## When environments are created

The worker provisions a new environment when:

* a run starts and no matching environment exists,
* the environment is missing on disk, or
* dependency manifests changed (new `deps_digest`).

---

## GC and cleanup

Environment cleanup is worker-owned. The GC policy deletes **non-active**
configuration environments that are cold (older than TTL) and unused by
queued/running runs. See `apps/ade-worker/README.md` for details.
