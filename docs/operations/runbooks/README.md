---
Audience: Platform administrators, support teams
Goal: Provide structured incident response steps for ADE operational issues.
Prerequisites: Admin access to ADE, ability to run CLI commands, and visibility into deployment telemetry.
When to use: Open when responding to an active incident or rehearsing operational drills.
Validation: Confirm each runbook uses the Triggers → Diagnostics → Resolution → Validation → Escalation structure.
Escalate to: Support lead or site reliability contact when incidents exceed documented playbooks.
---

# Operations runbooks

Runbooks apply a consistent structure so responders can triage ADE incidents quickly. Each guide starts with triggers that justify invoking the runbook, then lists diagnostics and recovery steps.

## Current runbooks

- [Expired document purge](./expired-document-purge.md)

## Planned additions (TODO)

- `storage-capacity.md`
- `sso-outage.md`
- `admin-access-recovery.md`
