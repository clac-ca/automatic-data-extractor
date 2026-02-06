# Release Process

## Purpose

Explain how ADE versions and images are produced, and how operators deploy a specific version.

## Source of Truth

- commit history (Conventional Commits)
- `VERSION`
- `CHANGELOG.md`
- release config in `.github/release-please/`

## Automated Flow

1. Release workflow runs on configured branch events.
2. Release Please creates or updates release PRs.
3. Merged release PR updates version/changelog and creates tags.
4. Docker workflow publishes images for branches and tags.

## Current Workflow Targets

- `release-please.yaml` runs on pushes to `main`.
- `docker-image.yaml` publishes on `main`, `development`, and `v*` tags.

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

## Compose Note (Self-Hosted Only)

If you run self-hosted compose production, use `ADE_DOCKER_TAG`:

```bash
ADE_DOCKER_TAG=vX.Y.Z docker compose -f docker-compose.prod.yaml up -d
```

## Operator Checklist

1. Confirm target tag exists.
2. Run migrations once.
3. Deploy the image to `ade-app`.
4. Verify health and one run flow.
5. Record deployed tag and timestamp.
