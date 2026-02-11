# Release Process

## Purpose

Explain how ADE versions and container images are produced, including rebuild releases.

## Source of Truth

- commit history (Conventional Commits)
- `VERSION`
- `CHANGELOG.md`
- release config in `.github/release-please/`

## Automated Flow

1. `release-please.yaml` runs on pushes to `main`.
2. Release Please creates or updates release PRs.
3. Merging the release PR updates `VERSION`/`CHANGELOG` and creates GitHub release tag `vX.Y.Z`.
4. Publishing that release triggers `docker-image.yaml` and publishes images.

## Current Workflow Targets

- `release-please.yaml` runs on pushes to `main`.
- `docker-image.yaml` publishes on:
  - pushes to `main` and `development`
  - published GitHub releases

## Image Tag Policy

### Branch channels
- `main` (moving)
- `development` (moving)

### Stable releases (`vX.Y.Z`)
- Immutable tag: `vX.Y.Z`
- Convenience aliases: `X.Y.Z`, `X.Y`, `X`, `latest`

### Rebuild releases (`vX.Y.Z-rN`)
- Immutable tag: `vX.Y.Z-rN`
- Rebuilds do **not** move `X.Y.Z` (exact semver alias is frozen on stable release)

## Rebuild Flow

Use workflow dispatch on `.github/workflows/rebuild-release.yaml`:

1. Input `base_release_tag=vX.Y.Z`.
2. Input `reason=<short reason>`.
3. Workflow auto-selects next rebuild suffix (`-rN`), creates tag, and creates a prerelease.
4. Prerelease publish triggers `docker-image.yaml` for rebuild tag publishing.

## Immutability Rules

- Do not overwrite existing `vX.Y.Z` tags.
- Do not overwrite existing `vX.Y.Z-rN` tags.
- Enforce protected tags for `v*` in repository settings.

## Deploying a Specific Version (Azure Container Apps)

```bash
RG=<resource-group>
APP_NAME=ade-app
IMAGE=ghcr.io/<org>/<repo>:vX.Y.Z

az containerapp update --name "$APP_NAME" --resource-group "$RG" --image "$IMAGE"
```

For branch tip deployments:

```bash
IMAGE=ghcr.io/<org>/<repo>:main
```

For rebuild deployments:

```bash
IMAGE=ghcr.io/<org>/<repo>:vX.Y.Z-rN
```

## Compose Note (Self-Hosted Only)

If you run self-hosted compose production, use `ADE_DOCKER_TAG`:

```bash
ADE_DOCKER_TAG=vX.Y.Z docker compose -f docker-compose.prod.yaml up -d
```

For rebuilds:

```bash
ADE_DOCKER_TAG=vX.Y.Z-rN docker compose -f docker-compose.prod.yaml up -d
```

## GHCR Cleanup

- Cleanup is manual only via `.github/workflows/ghcr-package-cleanup.yaml`.
- Use dry-run first, then live mode.
- Cleanup removes only old unreachable untagged versions (retention-based).

## Operator Checklist

1. Confirm target tag exists.
2. Run migrations once.
3. Deploy the image to `ade-app`.
4. Verify health and one run flow.
5. Record deployed tag and timestamp.
