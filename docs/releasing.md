# Releasing ADE (manual tags)

This repo publishes a Docker image to **GitHub Container Registry (GHCR)** via GitHub Actions.

A “release” is a **git tag** of the form `vX.Y.Z` (Semantic Versioning).

> The Docker workflow builds/pushes on:
> - pushes to `main` (tagged as `main` + `sha-...`)
> - version tags `v*` (tagged as `1.2.3`, `1.2`, `1`, and typically `latest`)

---

## 1) Pre-release sanity

- [ ] `main` is green (CI passing).
- [ ] No unreviewed/unfinished migrations are pending.
- [ ] `docker-compose.yml` still works from scratch (fresh clone).
- [ ] Confirm the intended release version follows SemVer:
  - MAJOR = breaking change
  - MINOR = new functionality, backwards compatible
  - PATCH = bug fix, backwards compatible

## 2) Prepare release notes

- [ ] Identify the PRs/issues included since last release.
- [ ] Draft a short “What’s new” section and a “Breaking changes” section (if any).
- [ ] Note any required config changes (env vars, compose changes).
- [ ] If API behavior changed, ensure README/docs are updated.

## 3) Local verification (recommended)

From a clean working tree:

- [ ] Build the production image:
  ```bash
  bash scripts/docker/build-image.sh
  ```
- [ ] Run quickstart stack:
  ```bash
  docker compose -f docker-compose.yml up
  ```
- [ ] Verify API responds and worker starts cleanly.
- [ ] (Optional) Run `ade init` provisioning (DB create) inside the container if applicable.

## 4) Create and push the tag

- [ ] Create an annotated tag:
  ```bash
  git tag -a vX.Y.Z -m "Release vX.Y.Z"
  ```
- [ ] Push the tag:
  ```bash
  git push origin vX.Y.Z
  ```

## 5) Watch GitHub Actions

- [ ] Confirm `Docker Image (GHCR)` workflow runs on the tag and publishes images.
- [ ] Confirm tags exist in GHCR:
  - `ghcr.io/clac-ca/automatic-data-extractor:1.2.3`
  - `ghcr.io/clac-ca/automatic-data-extractor:1.2`
  - `ghcr.io/clac-ca/automatic-data-extractor:1`
  - `ghcr.io/clac-ca/automatic-data-extractor:latest` (if configured)

## 6) Create/verify GitHub Release

- [ ] Confirm `Release` workflow created a GitHub Release (or create it manually).
- [ ] Paste release notes (What’s new + upgrade notes).
- [ ] Link to the images and quickstart instructions.

## 7) Post-release follow-ups

- [ ] Announce release (if applicable).
- [ ] Open issues for any follow-up cleanup.
- [ ] If a hotfix is needed, repeat as `vX.Y.(Z+1)`.
