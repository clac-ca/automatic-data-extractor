# 🔄 Next Task — Document and smoke-test the new ADE CLI entrypoint

## Context
The authentication commands now live behind a shared `backend.app.cli` module and can be invoked with `python -m backend.app`.
Documenting the workflow and adding a light integration test will help future contributors discover and trust the CLI.

## Goals
1. Update the relevant documentation (README or DOCUMENTATION.md) with examples showing how to run `python -m backend.app auth ...`.
2. Add a quick integration test that invokes the new top-level CLI entry point (e.g. `backend.app.cli.main([...])`) to ensure the wiring works.
3. Keep existing auth CLI behaviours intact; the new test should reuse the configured SQLite fixture.

## Definition of done
- Documentation clearly explains how to reach the ADE CLI and the available auth subcommands.
- A test covers the `backend.app.cli.main()` path to guard the new entry point.
- `pytest backend/tests/test_auth.py` continues to pass.
