# Migrate to Release-Tagged Images With Manual Azure Deploys

## Goal

Move ADE toward a simpler release model in two stages.

Stage 1, covered by this guide:

```text
feature branch -> PR -> main -> GitHub release tag -> GHCR image -> manual Azure revision deploy
```

Stage 2, later:

```text
feature branch -> PR -> main -> GitHub release tag -> GHCR image -> approved automatic Azure deploy
```

For now, GitHub Actions should only build and publish the release image. A human operator manually updates the Azure Container App revision after confirming the image exists.

End state for this stage:

- `main` becomes the only long-lived integration branch.
- There is no standing development release channel.
- PR checks prove changes before merge.
- Published GitHub releases create tagged GHCR images such as `ghcr.io/clac-ca/automatic-data-extractor:v1.17.0`.
- Production deploys are manual Azure Container App image updates.
- Azure infrastructure changes stay separate from app releases.

## Before You Start

Required local tools:

```bash
az version
gh --version
docker --version
git --version
```

Sign in:

```bash
az login --use-device-code
gh auth login
```

Set local variables:

```bash
OWNER="clac-ca"
REPO="automatic-data-extractor"
GH_REPO="$OWNER/$REPO"
RG="rg-ade-shared-canadacentral-001"

az account show --query "{subscriptionId:id,tenantId:tenantId,user:user.name}" --output table
```

If the resource group changes, find it with:

```bash
az group list --query "[].{name:name,location:location}" --output table
```

## Step 1: Capture The Current Production App

List Container Apps:

```bash
az containerapp list \
  --resource-group "$RG" \
  --query "[].{name:name,fqdn:properties.configuration.ingress.fqdn,image:properties.template.containers[0].image}" \
  --output table
```

Set the production app:

```bash
APP_NAME="ca-ade-prod-canadacentral-001"
APP_FQDN="$(az containerapp show \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --query "properties.configuration.ingress.fqdn" \
  -o tsv)"
ADE_PUBLIC_WEB_URL="$(az containerapp show \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --query "properties.template.containers[0].env[?name=='ADE_PUBLIC_WEB_URL'].value | [0]" \
  -o tsv)"
if [ -z "$ADE_PUBLIC_WEB_URL" ]; then
  ADE_PUBLIC_WEB_URL="https://$APP_FQDN"
fi
CURRENT_IMAGE="$(az containerapp show \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --query "properties.template.containers[0].image" \
  -o tsv)"

printf 'RG=%s\nAPP_NAME=%s\nADE_PUBLIC_WEB_URL=%s\nCURRENT_IMAGE=%s\n' \
  "$RG" "$APP_NAME" "$ADE_PUBLIC_WEB_URL" "$CURRENT_IMAGE"
```

For the current production deployment, this should resolve to:

```text
APP_NAME=ca-ade-prod-canadacentral-001
ADE_PUBLIC_WEB_URL=https://ade.clac.ca
CURRENT_IMAGE=ghcr.io/clac-ca/automatic-data-extractor:1.16.0
```

Save `CURRENT_IMAGE`. It is the rollback target for the first manual release deploy.

Verify production is healthy before changing anything:

```bash
curl -fsS "$ADE_PUBLIC_WEB_URL/api/v1/health"
curl -fsS "$ADE_PUBLIC_WEB_URL/api/v1/info"
```

## Step 2: Confirm Production App Shape

Check current runtime settings:

```bash
az containerapp show \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --query "properties.template.containers[0].env[].{name:name,value:value,secretRef:secretRef}" \
  --output table
```

Production should have:

```text
ADE_SERVICES=api,worker,web
ADE_PUBLIC_WEB_URL=https://ade.clac.ca
ADE_AUTH_DISABLED=false
ADE_DATA_DIR=/app/data
ADE_BLOB_CONTAINER=ade-prod
ADE_BLOB_ACCOUNT_URL=<storage account blob URL>
ADE_DATABASE_URL=<secretRef>
ADE_SECRET_KEY=<secretRef>
```

For future Azure infra reruns, make sure the local deploy script uses:

```bash
deploy_development_environment="false"
```

That line belongs in `infra/azure/deploy.sh`; it is not a standalone terminal command.

Do not delete existing development Azure resources yet. Clean them up only after the release/manual-deploy path succeeds.

## Step 3: Use The Existing Release Image Publisher

Release image publishing is owned by `.github/workflows/docker-image.yaml`.

That workflow:

- runs on published GitHub releases
- publishes GHCR release tags
- preserves immutable release and rebuild tag behavior
- does not log in to Azure or deploy production

Do not add a second release-published image workflow. Production deployment stays manual until a separate automatic Azure deployment model is chosen.

## Step 4: Keep One Docker Publishing Workflow

Keep `.github/workflows/docker-image.yaml` as the only GHCR image publishing workflow.

Remove any temporary release-only image workflow after confirming `docker-image.yaml` publishes the needed release tags.

## Step 5: Publish The First Low-Risk Release Image

Use a low-risk release first. A docs-only release is ideal.

Find existing release tags:

```bash
gh release list --repo "$GH_REPO" --limit 10
```

Choose the next patch tag:

```bash
NEW_TAG="v1.16.1"
```

If the next real release should be different, set `NEW_TAG` to that value.

Create a draft release:

```bash
gh release create "$NEW_TAG" \
  --repo "$GH_REPO" \
  --target main \
  --title "$NEW_TAG" \
  --generate-notes \
  --draft
```

Open the draft release in GitHub, review the generated notes, and publish it.

Watch the image workflow:

```bash
gh run list --repo "$GH_REPO" --workflow docker-image.yaml --limit 5
gh run watch --repo "$GH_REPO" --exit-status
```

Confirm the image exists in GHCR:

```bash
docker buildx imagetools inspect "ghcr.io/$GH_REPO:$NEW_TAG"
```

At this point production has not changed. Azure is still running `CURRENT_IMAGE`.

## Step 6: Manually Deploy The Release Image To Azure

Set the new image:

```bash
NEW_IMAGE="ghcr.io/$GH_REPO:$NEW_TAG"
```

Run migrations against the currently deployed app:

```bash
az containerapp exec \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --command "ade db migrate"
```

Deploy the new image revision:

```bash
az containerapp update \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --image "$NEW_IMAGE"
```

Confirm Azure is running the new image:

```bash
az containerapp show \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --query "properties.template.containers[0].image" \
  -o tsv
```

Smoke test:

```bash
curl -fsS "$ADE_PUBLIC_WEB_URL/api/v1/health"
curl -fsS "$ADE_PUBLIC_WEB_URL/api/v1/info"
```

If rollback is needed:

```bash
az containerapp update \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --image "$CURRENT_IMAGE"
```

Record the deployment:

```text
release tag:
deployed image:
previous image:
deployment timestamp:
operator:
health check result:
rollback notes:
```

## Step 7: Move PRs And Default Branch To Main

After one manual production deploy from a release image succeeds, change GitHub branch settings.

In GitHub UI:

1. Open `https://github.com/clac-ca/automatic-data-extractor/settings/branches`.
2. Make sure `main` has branch protection.
3. Require the PR gate checks that currently protect `development`.
4. Open `https://github.com/clac-ca/automatic-data-extractor/settings`.
5. Change the default branch from `development` to `main`.

Update local branches:

```bash
git fetch origin
git checkout main
git pull --ff-only
```

Update Dependabot to target `main`:

```yaml
target-branch: "main"
```

Files to update:

```text
.github/dependabot.yaml
AGENTS.md
CONTRIBUTING.md
docs/reference/release-process.md
docs/how-to/new-deployment-setup.md
```

Search for remaining `development` branch instructions:

```bash
rg -n "development|target-branch|promotion|Release Please|release-please" AGENTS.md CONTRIBUTING.md docs .github
```

Patch only the docs/workflows that are part of the deployment migration.

## Step 8: Remove Old Promotion Machinery

Create a cleanup branch from `main`:

```bash
git checkout main
git pull --ff-only
git checkout -b codex/remove-development-promotion-flow
```

Remove the main promotion guardrail:

```bash
git rm .github/workflows/main-promotion-release-guardrail.yaml
```

Update `.github/workflows/ci-pr-gates.yaml` so pushes run on `main` instead of `development`:

```yaml
on:
  pull_request:
  push:
    branches: [main]
```

Update `.github/workflows/docker-image.yaml` so branch publishing no longer publishes a `development` tag:

```yaml
on:
  pull_request:
    paths:
      - "Dockerfile"
      - ".dockerignore"
      - "docker-compose.yaml"
      - "docker-compose.prod.yaml"
      - "docker-compose.prod.split.yaml"
      - ".devcontainer/**"
      - "scripts/**"
      - ".github/workflows/docker-image.yaml"
  push:
    branches: [main]
  release:
    types: [published]
  workflow_dispatch:
```

Remove the `development` Docker metadata tag block from that workflow.

Update Dependabot auto-merge to require `github.base_ref == 'main'` instead of `development`.

Run checks:

```bash
git diff --check
```

Commit and open PR:

```bash
git add .github AGENTS.md CONTRIBUTING.md docs
git commit -m "chore(deploy): remove development promotion flow"
git push -u origin codex/remove-development-promotion-flow
gh pr create --base main --title "chore(deploy): remove development promotion flow" --body "Moves deployment docs and workflow triggers to the single-main release model."
```

## Step 9: Choose Release Please Or Native GitHub Releases

Choose one release source.

### Option A: Native GitHub Releases

Use this if maintainers want the simplest model.

Remove Release Please:

```bash
git checkout main
git pull --ff-only
git checkout -b codex/remove-release-please
git rm .github/workflows/release-please.yaml
git rm -r .github/release-please
```

Decide how to handle:

```text
VERSION
CHANGELOG.md
```

Recommended native-release options:

- keep `VERSION` only if the app reads it and update it in release PRs
- keep `CHANGELOG.md` only if operators actively use it
- otherwise treat GitHub Releases as the release notes source of truth

Commit:

```bash
git add VERSION CHANGELOG.md docs CONTRIBUTING.md AGENTS.md
git commit -m "chore(release): use native GitHub releases"
git push -u origin codex/remove-release-please
gh pr create --base main --title "chore(release): use native GitHub releases" --body "Removes Release Please after production deploys move to release-published images."
```

### Option B: Keep Release Please

Use this if you still want automated `VERSION` and `CHANGELOG.md` updates.

Keep:

```text
.github/workflows/release-please.yaml
.github/release-please/
VERSION
CHANGELOG.md
```

Update docs to say:

```text
merge PRs to main -> Release Please PR -> merge Release Please PR -> GitHub release -> GHCR image -> manual Azure deploy
```

## Step 10: Clean Up Azure Development Resources

Only do this after production has deployed successfully from a release image and no one needs the development app.

List development resources:

```bash
az containerapp list \
  --resource-group "$RG" \
  --query "[?contains(name, '-dev-')].{name:name,image:properties.template.containers[0].image}" \
  --output table

az postgres flexible-server db list \
  --resource-group "$RG" \
  --server-name "<postgresql-server-name>" \
  --query "[].name" \
  --output table

az storage container list \
  --account-name "<storage-account-name>" \
  --auth-mode login \
  --query "[].name" \
  --output table

az storage share-rm list \
  --resource-group "$RG" \
  --storage-account "<storage-account-name>" \
  --query "[].name" \
  --output table
```

If development data is useful, export or snapshot it before deletion.

Delete the development Container App:

```bash
az containerapp delete \
  --resource-group "$RG" \
  --name "<development-container-app-name>"
```

Delete development storage only after confirming it is not used by production:

```bash
az storage container delete \
  --account-name "<storage-account-name>" \
  --name "<development-blob-container-name>" \
  --auth-mode login

az storage share-rm delete \
  --resource-group "$RG" \
  --storage-account "<storage-account-name>" \
  --name "<development-file-share-name>"
```

Delete the development database only after confirming no app uses it:

```bash
az postgres flexible-server db delete \
  --resource-group "$RG" \
  --server-name "<postgresql-server-name>" \
  --database-name "<development-database-name>"
```

Do not delete shared resources that production still uses:

- resource group
- Container Apps managed environment
- VNet/subnets
- Log Analytics workspace
- PostgreSQL server
- Storage Account
- production blob container
- production Azure Files share

## Step 11: Delete The Development Branch

Only after:

- default branch is `main`
- open PRs no longer target `development`
- branch protection no longer requires `development`
- Dependabot targets `main`
- a release image has been manually deployed successfully

Delete remote branch:

```bash
git push origin --delete development
```

Delete local branch:

```bash
git branch -d development
```

## Later: Automatic Azure Deploys

After manual release deploys are stable, choose one automatic production deployment model:

- GitHub Actions OIDC to Azure with a protected `production` environment
- Azure Container Apps Jobs for migrations, then Container App image update
- Azure-native deployment pipeline triggered from release tags

Do not add Azure OIDC, production environment variables, or automated Container App updates until that decision is made.

## Final Operating Rule

```text
main is always releasable.
production only runs releases.
GHCR stores the built image.
Azure Container Apps runs that image after a manual revision update.
Azure infra changes are separate from app deploys.
image publishing is automated; production deployment is manual until this path is stable.
```
