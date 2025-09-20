---
Audience: Platform administrators
Goal: Outline deployment and operational tasks that keep ADE healthy across local, Docker, and hosted environments.
Prerequisites: Access to infrastructure credentials and the ADE repository.
When to use: Review before installing ADE, rotating secrets, or planning an environment upgrade.
Validation: Confirm links to the quickstart, environment management, security, and operations guides resolve without 404s.
Escalate to: Platform owner or DevOps lead when deployment steps drift from the implemented infrastructure.
---

# Platform operations overview

Platform administrators assemble, deploy, and maintain ADE. Start with the guides below to get a local instance running and your configuration under control, then branch into security and operations.

## Core guides

1. [Local quickstart (Windows PowerShell)](./quickstart-local.md) — spin up ADE on a laptop without Docker.
2. [Environment and secret management](./environment-management.md) — structure `.env` files, rotate secrets, and restart safely.
3. [Document retention policy](../operations/document-retention.md) — understand purge cadences before exposing ADE to production data.
4. [Authentication modes](../security/authentication-modes.md) — choose the right auth strategy ahead of deployment.
5. [SSO setup and recovery](../security/sso-setup.md) — configure and maintain OIDC integration when `sso` mode is enabled.

## Expand your context

- [Foundation overview](../foundation/README.md) — architecture context and glossary references.
- [Security overview](../security/README.md) — review baseline controls and upcoming hardening work.
- [Operations runbooks](../operations/runbooks/README.md) — hands-on responses for retention, storage, and purge tasks.

## Upcoming guides (TODO)

- `azure-container-apps.md` — hosted deployment walkthrough.
- Incident playbooks for container health and infrastructure upgrades.
