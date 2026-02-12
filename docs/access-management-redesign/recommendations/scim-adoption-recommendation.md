# SCIM Adoption Recommendation

## Recommendation

Implement SCIM 2.0 as the enterprise provisioning channel in ADE while keeping invitation and JIT as alternative provisioning modes.

Selected model:

1. Provisioning mode `scim` enables standardized `/scim/v2` lifecycle endpoints.
2. Provisioning mode `jit` remains available for organizations that cannot deploy SCIM.
3. Provisioning mode `disabled` remains available for invite-only operation.

## Why This Is the Best Fit

1. Aligns with enterprise standards and IdP integrations (Entra/Okta).
2. Reduces bespoke sync logic and ownership ambiguity.
3. Keeps code easier to reason about via explicit mode-based behavior.

## SCIM Endpoint Profile (Phase 1)

Base path: `/scim/v2`

Required discovery endpoints:

1. `GET /ServiceProviderConfig`
2. `GET /Schemas`
3. `GET /ResourceTypes`

User endpoints:

1. `GET /Users`
2. `POST /Users`
3. `GET /Users/{id}`
4. `PATCH /Users/{id}`
5. `PUT /Users/{id}` (optional in first pass, recommended)

Group endpoints:

1. `GET /Groups`
2. `POST /Groups`
3. `GET /Groups/{id}`
4. `PATCH /Groups/{id}`
5. `PUT /Groups/{id}` (optional in first pass, recommended)

Not included in first pass:

1. `/Bulk`

Primary references:

- [RFC 7644](https://datatracker.ietf.org/doc/html/rfc7644)
- [RFC 7643](https://datatracker.ietf.org/doc/html/rfc7643)

## Resource Mapping to ADE

### SCIM User -> ADE user

- `userName`/`emails` -> `email`, `email_normalized`
- `name.givenName` -> `given_name`
- `name.familyName` -> `surname`
- `title` -> `job_title`
- `phoneNumbers` -> `mobile_phone`/`business_phones`
- `urn:ietf:params:scim:schemas:extension:enterprise:2.0:User` fields -> department, employee metadata
- `active=false` -> user deactivation
- `externalId` + SCIM `id` -> correlation metadata

### SCIM Group -> ADE group

- `displayName` -> `display_name`
- `members` -> `group_memberships` for known/provisioned users
- Group objects from SCIM are provider-managed/read-only in ADE membership UI.

## Authentication and Security Model

1. SCIM uses dedicated bearer tokens scoped to provisioning endpoints.
2. SCIM credentials are separate from interactive user sessions.
3. All SCIM mutations are audit logged with request correlation IDs.

## Behavioral Guardrails

1. No implicit user creation from non-SCIM background group membership data.
2. In `scim` mode, SSO callback should not JIT-create unknown users.
3. In `jit` mode, membership hydration is per-user-on-sign-in only.

## Operational Guidance

1. Start with Entra + Okta compatibility (filter/pagination/patch semantics they use).
2. Publish SCIM integration guide with tested attribute mappings.
3. Add conformance integration tests for Entra and Okta happy paths.

## Migration Guidance Constraint

Because hard-cutover migration `0002_access_model_hard_cutover` is not yet deployed, any required schema change should update this migration file in place:

- `backend/src/ade_db/migrations/versions/0002_access_model_hard_cutover.py`

Do not add a new migration revision for this iteration.
