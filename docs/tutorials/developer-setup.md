# Developer Setup (Fast Path)

## Goal

Get contributors coding in ADE with the smallest number of steps.

This guide shows two setup scenarios:

1. `.devcontainer` (recommended)
2. Manual local setup

## Clone the Repo (Both Scenarios)

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor
```

## Prerequisites

### `.devcontainer` (recommended)

- Git
- Docker (with Docker Compose)
- IDE with dev container support (for example, VS Code + Dev Containers extension)

### Manual local setup

- Git
- Docker (with Docker Compose)
- Python `>=3.13,<3.15`
- Node.js `>=20,<23`
- `uv`

## Scenario 1: `.devcontainer` (Recommended)

### Why this is recommended

- Most setup is automated.
- Consistent runtime across contributors.
- Fewer local machine dependency issues.

### Minimal IDE command

Run on your host machine:

```bash
code .
```

Then in your IDE, reopen the project in the dev container.

Inside the container terminal, run:

```bash
cd backend && uv run ade dev
```

Open:

- `http://localhost:8000`

## Scenario 2: Manual Local Setup

### Minimal terminal commands

From repo root:

```bash
./setup.sh --with-infra
cd backend && uv run ade dev
```

Open:

- `http://localhost:8000`

### Useful follow-up commands

Show resolved local infra details:

```bash
cd backend && uv run ade infra info
```

Stop local infra:

```bash
cd backend && uv run ade infra down
```

Full local infra reset:

```bash
cd backend && uv run ade infra down -v --rmi all
```

## Copy/Paste Quick Start Blocks

### Recommended (`.devcontainer`)

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor
code .
# Reopen in dev container from your IDE, then:
cd backend && uv run ade dev
```

### Manual

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor
./setup.sh --with-infra
cd backend && uv run ade dev
```

## Next Step

- For deeper contributor commands and workflows, see [Run Local Dev Loop](../how-to/run-local-dev-loop.md).
