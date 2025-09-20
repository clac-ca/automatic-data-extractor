---
Audience: Platform administrators, support teams
Goal: Document recurring operational tasks, retention policies, and incident response entry points for ADE.
Prerequisites: Access to ADE runtime logs, database, and document storage along with admin credentials.
When to use: Consult when maintaining document hygiene, running scheduled maintenance, or responding to operational alerts.
Validation: Check the policy guide and runbook links resolve and record TODO placeholders for upcoming runbooks.
Escalate to: Platform owner or support lead if operational procedures fall out of sync with production behaviour.
---

# Operations

Operations content covers the day-to-day stewardship of ADE once it is running. Start with the retention policy to understand how documents are managed, then use the runbooks when responding to incidents.

## Available material

- [Document retention policy](./document-retention.md) — explains default windows, overrides, scheduler behaviour, and supporting code paths.
- [Expired document purge runbook](./runbooks/expired-document-purge.md) — incident response for manual purges and scheduler validation.

## Planned runbooks (TODO)

- `storage-capacity.md` — reclaim disk space and coordinate with storage owners.
- `sso-outage.md` — stabilise authentication when the identity provider is unavailable.
