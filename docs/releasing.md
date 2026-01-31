# Releasing ADE (Release Please)

ADE uses **Release Please** (manifest mode) to manage versions for the bundled
Docker image and each component. Releases happen from the `development` branch.
Release Please config lives in `.github/release-please/`.

## Version sources

- **Image (bundle) version**: root `VERSION`
- **API version**: `apps/ade-api/pyproject.toml`
- **Web version**: `apps/ade-web/package.json`
- **Worker version**: `apps/ade-worker/pyproject.toml`

The bundle changelog lives at `CHANGELOG.md`. Component changelogs are not
maintained (components are versioned, but only the bundle changelog is updated).

## Tag conventions

Git tags:
- **Image/bundle tag**: `vX.Y.Z`
- **Component tags**:
  - `ade-api-vX.Y.Z`
  - `ade-web-vX.Y.Z`
  - `ade-worker-vX.Y.Z`

Docker image tags (from the `vX.Y.Z` release tag):
- `X.Y.Z`, `X.Y`, `X`
- `latest` (release tags only)

## Release flow (standard)

1) Merge feature/fix PRs into `development` using **Conventional Commits**.
2) Release Please opens (or updates) a **Release PR** on `development`.
3) Review and merge the Release PR.
4) Release Please creates tags:
   - `vX.Y.Z` for the image
   - `ade-*-vX.Y.Z` for components that changed
5) The Docker workflow builds/pushes images when the tag is created.

## Token note

To ensure that tags created by Release Please trigger other workflows
(e.g. Docker builds), set a PAT in `RELEASE_PLEASE_TOKEN`. The default
`GITHUB_TOKEN` does **not** trigger downstream workflows on tag creation.

## Quick sanity (optional)

- `docker compose -f docker-compose.yaml up --build`
- Verify API health and worker startup logs
