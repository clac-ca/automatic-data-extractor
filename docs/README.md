---
Audience: All personas
Goal: Provide a persona-oriented hub that routes every reader to the correct ADE documentation slice.
Prerequisites: Access to this repository or the in-app documentation viewer.
When to use: Start here whenever you need to find setup, operations, or workflow guidance for ADE.
Validation: Visit each persona card below and confirm the linked README plus at least one guide renders without 404s.
Escalate to: Documentation maintainers (platform administrators) when navigation is broken or personas lack coverage.
---

# ADE documentation hub

ADE’s documentation is organised around the core personas described in [DOCUMENTATION.md](../DOCUMENTATION.md). Each section keeps the same metadata block so you always see audience, prerequisites, and escalation paths before diving in. Start with the stable foundation references below to anchor yourself on architecture choices that rarely change, then jump to the persona workflow that matches the job at hand.

## Stable foundation references

- [Foundational architecture overview](./foundation/README.md) — systems context, glossary entry points, and recommended reading order.
- [System overview](./foundation/system-overview.md) — component boundaries, lifecycle summary, and integration touchpoints.
- [Environment variables reference](./reference/environment-variables.md) — canonical list of runtime toggles that the UI surfaces.

## How to use this hub

1. Identify the persona that matches your task.
2. Follow the **Entry point** link to the section README for context and reading order.
3. Jump into the listed guides or runbooks to complete the job.
4. Return here when you need to switch personas or find another task.

## Persona quick links

### Platform administrators
- **Entry point:** [Platform operations overview](./platform/README.md)
- **Key guides:**
  - [Local quickstart (Windows PowerShell)](./platform/quickstart-local.md)
  - [Environment and secret management](./platform/environment-management.md)
  - [Authentication modes](./security/authentication-modes.md)
  - [SSO setup and recovery](./security/sso-setup.md)
  - [Document retention policy](./operations/document-retention.md)
- **Runbooks:**
  - [Expired document purge](./operations/runbooks/expired-document-purge.md)
  - Storage capacity recovery (TODO)

### IT architects
- **Entry point:** [Foundational architecture overview](./foundation/README.md)
- **Key guides:**
  - [System overview](./foundation/system-overview.md)
  - [Security overview](./security/README.md)
  - [Glossary](../ADE_GLOSSARY.md)
- **Runbooks:**
  - SSO outage recovery (TODO)
  - Change approval checklist (TODO)

### Support & configuration managers
- **Entry point:** [Configuration workflows](./configuration/README.md)
- **Key guides:**
  - [Configuration concepts](./configuration/concepts.md)
  - [Publishing and rollback](./configuration/publishing-and-rollback.md)
  - Authoring guide (TODO)
- **Runbooks:**
  - Rollback verification (TODO)
  - Configuration export/import (TODO)

### Data teams
- **Entry point:** [Integration surface](./data-integration/README.md)
- **Key guides:**
  - [API overview](./data-integration/api-overview.md) — highlights the upcoming API key flow alongside the current session-based fallback.
  - [Environment variables reference](./reference/environment-variables.md)
  - SQL access recipes (TODO)
- **Runbooks:**
  - Data export validation (TODO)
  - Event feed troubleshooting (TODO)

### End users
- **Entry point:** [User workflow primer](./user-guide/README.md)
- **Key guides:**
  - Upload and queue documents (TODO)
  - Monitor and review jobs (TODO)
  - Download and share outputs (TODO)
- **Runbooks:**
  - UI troubleshooting checklist (TODO)
  - When to escalate to support (TODO)

## Assets and diagrams

Architecture diagrams, UI screenshots, and other artefacts live under [docs/assets](./assets/README.md). Update the index there whenever you add or revise an image so readers know which guide owns the asset and when it was last validated.
