# Frontend Access UI Gap Analysis (Research Refresh)

Date: February 12, 2026

## Summary

ADE access UI still has first-class usability gaps despite route/API improvements.
The highest-impact issues are membership editability, action affordance clarity,
and cross-surface coherence.

## Current ADE Gaps (Validated)

| Gap | Current state | Impact | Gap class |
| --- | --- | --- | --- |
| Group detail cannot fully manage members | Group drawer shows member list but no first-class add/remove member controls | Admins cannot complete group lifecycle from group context | UI-only |
| User detail cannot directly manage group memberships | No dedicated groups tab/actions on user detail | User-centric troubleshooting takes too many clicks | UI + candidate API extension |
| Non-clickable/disabled actions can be unclear | Disabled states are present but not consistently reasoned | Perceived broken UI and low trust | Policy/permission copy + UI contract |
| Command surfaces are inconsistent by page | Users/principals/invitations use newer command pattern; groups/roles still mixed | Inconsistent mental model and slower operation | UI-only |
| Membership source boundaries are not prominent enough | Provider-managed states are not always first-class in all surfaces | Admin confusion on why edits fail | UI-only |
| Cross-linking between users/groups/principals is weak | Limited direct navigation between related entities | Excessive context switching | UI-only |

## Capability Parity Check (API vs UI)

Already available in API:

1. Group-centric member mutations exist (`/groups/{id}/members/$ref` add/remove).
2. Role assignment APIs support principal-aware assignments across org/workspace.

Missing for ideal user-centric UX:

1. No user-centric `memberOf` endpoints to efficiently power user->groups management.

Conclusion:

1. Most immediate pain points are UI execution gaps.
2. One small API extension would materially simplify user-detail membership management.

## Benchmark Delta (Entra + peers)

Compared with benchmark patterns:

1. ADE lacks first-class group-detail membership operations.
2. ADE lacks user-detail group-membership operations.
3. ADE has partial command-bar consistency, not full-surface consistency.
4. ADE needs a formal disabled-state contract with deterministic reasons.

## Recommended Priority Order

1. P0: Group detail member management (add/remove + provider-managed guardrails).
2. P0: User detail group membership management (add/remove memberships).
3. P1: Affordance model for disabled/hidden states.
4. P1: Cross-surface command-bar and action hierarchy consistency.
5. P2: Optional user-centric membership endpoints for scale/performance.

## Candidate Interface Delta

1. `No change required` for group-detail member management (already supported API).
2. `Small extension recommended` for user-centric membership management:
   - `GET /api/v1/users/{userId}/memberOf`
   - `POST /api/v1/users/{userId}/memberOf/$ref`
   - `DELETE /api/v1/users/{userId}/memberOf/{groupId}/$ref`

## Sources

1. `docs/access-management-redesign/research/access-ui-task-flows-entra-plus-peers.md`
2. `docs/access-management-redesign/research/access-ui-competitive-patterns-matrix.md`
3. `docs/access-management-redesign/analysis/group-membership-ux-models.md`
4. `docs/access-management-redesign/analysis/action-affordance-and-disabled-state-model.md`
