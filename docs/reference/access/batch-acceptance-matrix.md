# Bulk User Acceptance Matrix

This matrix defines release-gate scenarios for `POST /api/v1/$batch` user lifecycle support.

## Functional Scenarios

| # | Scenario | Expected outcome |
| --- | --- | --- |
| 1 | Batch create 3 valid users | 3 item responses with `201`; users exist and are active |
| 2 | Batch update 3 existing users | 3 item responses with `200`; updated fields persisted |
| 3 | Batch deactivate 2 users | 2 item responses with `200`; users are inactive and access suppressed |
| 4 | Mixed create/update/deactivate in one envelope | Per-item statuses reflect each outcome; no cross-item bleed |
| 5 | Duplicate email create mixed with valid update | duplicate item `409`; other items succeed |
| 6 | One invalid payload in middle of batch | invalid item `422`; siblings still execute |
| 7 | One unauthorized item in mixed batch | unauthorized item `403`; authorized siblings still execute |
| 8 | Unknown user update/deactivate | item returns `404`; siblings unaffected |
| 9 | Dependency chain with failure (`dependsOn`) | dependent items return `424` |
| 10 | More than 20 requests | envelope rejected deterministically (`413` or `422` by contract) |

## Security and Policy Scenarios

| # | Scenario | Expected outcome |
| --- | --- | --- |
| 11 | Non-admin caller invokes batch user mutation | subrequests requiring `users.manage_all` fail with `403` |
| 12 | Workspace owner attempts global user mutations via batch | denied with `403` per subrequest |
| 13 | Browser session missing CSRF token | request rejected by same CSRF policy as direct mutation routes |
| 14 | Deactivated user retains direct/group role assignments | effective access remains denied |

## Operational Scenarios

| # | Scenario | Expected outcome |
| --- | --- | --- |
| 15 | Retry only failed items after partial success | replay succeeds without duplicating successful prior updates |
| 16 | Rate limit exceeded | request/subrequests return throttling status and retry signal |
| 17 | Metrics and logs inspection | batch and subrequest counters/logs present with correlation ids |
| 18 | OpenAPI + frontend type generation | generated contracts include batch schemas |

## Definition

All scenarios above must pass for bulk-user endpoint release readiness.
