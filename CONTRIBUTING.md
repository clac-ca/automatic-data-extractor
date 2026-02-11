# Contributing

## Branching

- Default branch: `development`
- Open PRs against `development`
- `main` is stable and updated via `development` merges

## Commit Messages

We use **Conventional Commits**:

- `feat:` new feature (minor)
- `fix:` bug fix (patch)
- `deps:` dependency updates (patch)
- `chore:` internal changes/docs (no release by default)

## Staging Discipline

- Only stage files related to the task
- Avoid bundling unrelated changes

## Testing

- Backend (unit): `ade api test`
- Backend (integration/all): `ade api test integration` or `ade api test all`
- Worker (unit): `ade worker test`
- Worker (integration/all): `ade worker test integration` or `ade worker test all`
- Frontend: `ade web test`
- Lint (backend): `ade api lint`
- Lint (frontend): `ade web lint`
- Full suite: `ade test`

## Releases

- Releases are handled automatically by **Release Please** on `main`
- Do not bump `VERSION` or `CHANGELOG.md` manually
- Version bumps are inferred from commit messages:
  - `fix:` / `deps:` -> patch
  - `feat:` -> minor
  - `feat!:` or `BREAKING CHANGE:` footer -> major
- If you need to force a version, use commit footer: `Release-As: X.Y.Z`
- Runtime version metadata (`ADE_APP_VERSION`, `ADE_APP_COMMIT_SHA`) is injected by CI; do not set these in `.env` for normal runtime config
- Deployable image versions are published as release tags (`vX.Y.Z`); production should deploy pinned tags via `ADE_DOCKER_TAG=vX.Y.Z`
- See `docs/reference/release-process.md` for details

## Quick Flows

### Normal release (hands-off)
1. Merge conventional commits to `main`.
2. Release Please opens/updates a release PR.
3. Merge the release PR.
4. GitHub release publish triggers container publish.

### Rebuild release (`vX.Y.Z-rN`)
1. Run the rebuild workflow (`.github/workflows/rebuild-release.yaml`) with:
   - `base_release_tag=vX.Y.Z`
   - `reason=<short reason>`
2. Workflow auto-creates next rebuild tag (`vX.Y.Z-rN`) and a prerelease.
3. Prerelease publish triggers container publish for rebuild tag only.

### PR merge to `development` (default)
1. Open PR against `development`.
2. Wait for required checks.
3. Merge PR (PR-first; avoid direct branch merges by default).

### Production pinning
- Preferred: pin by digest (`ghcr.io/<org>/<repo>@sha256:...`).
- Acceptable: immutable release tags (`vX.Y.Z` or `vX.Y.Z-rN`).

See `AGENTS.md` for coding-agent operational commands and `docs/reference/release-process.md` for full release/tag behavior.
