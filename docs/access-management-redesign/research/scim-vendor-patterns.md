# SCIM Vendor Patterns (Entra, Okta, GitHub, Atlassian)

## Purpose

Capture practical SCIM expectations from major IdPs/products so ADE can implement a standard, low-surprise SCIM surface.

## Standards Baseline (SCIM 2.0)

SCIM 2.0 defines canonical resource families and protocol behaviors:

- Discovery/config resources:
  - `/scim/v2/ServiceProviderConfig`
  - `/scim/v2/ResourceTypes`
  - `/scim/v2/Schemas`
- Core resources:
  - `/scim/v2/Users`
  - `/scim/v2/Groups`
- Standard behaviors:
  - filtering (`filter`)
  - pagination (`startIndex`, `count`)
  - partial updates (`PATCH`)

Sources:

- [RFC 7644: SCIM Protocol](https://datatracker.ietf.org/doc/html/rfc7644)
- [RFC 7643: SCIM Core Schema](https://datatracker.ietf.org/doc/html/rfc7643)

## Microsoft Entra Patterns

### What Entra expects

- SCIM endpoint implementation for app provisioning with Users and Groups.
- Schema + attribute mapping from Entra to app fields.
- Provisioning push model (Entra sends create/update/disable/group updates to app).

Sources:

- [Tutorial: develop and plan provisioning for a SCIM endpoint in Microsoft Entra ID](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)
- [Choose between Microsoft Graph and SCIM for user and group provisioning](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/scim-graph-scenarios)

### ADE implications

- SCIM should be the authoritative path when admins choose centralized lifecycle management.
- Do not mix “full directory polling + user creation” with SCIM mode; keep one provisioning authority.

## Okta Patterns

### What Okta expects

- SCIM integration with support for common operations (`GET`, `POST`, `PATCH`, deprovision via active state).
- Group push assumes users are already assigned/provisioned to the app.

Sources:

- [Okta SCIM provisioning integration overview](https://developer.okta.com/docs/guides/scim-provisioning-integration-overview/main/)
- [Okta SCIM protocol reference](https://developer.okta.com/docs/reference/scim/)
- [Okta group push prerequisites](https://help.okta.com/en-us/content/topics/users-groups-profiles/usgp-group-push-prerequisites.htm)

### ADE implications

- Group updates should not become implicit user-provisioning behavior.
- Unknown users referenced by group membership should be skipped until explicitly provisioned (SCIM) or signed in (JIT path).

## GitHub Patterns

### What GitHub demonstrates

- SCIM-backed identity lifecycle is explicit and enterprise-managed.
- Team sync aligns access groups with IdP groups, but identity lifecycle remains governed paths.

Sources:

- [About SCIM for organizations (GitHub)](https://docs.github.com/enterprise-cloud%40latest/organizations/managing-saml-single-sign-on-for-your-organization/about-scim-for-organizations)
- [Synchronizing a team with an identity provider group](https://docs.github.com/en/enterprise-cloud%40latest/organizations/organizing-members-into-teams/synchronizing-a-team-with-an-identity-provider-group)

### ADE implications

- Keep user provisioning and access-group synchronization conceptually separate.
- Treat provider-managed groups as read-only from ADE mutation endpoints.

## Atlassian Patterns

### What Atlassian demonstrates

- JIT provisioning is a viable fallback when SCIM is unavailable.
- SCIM provisioning is the recommended model for centralized enterprise lifecycle control.

Sources:

- [What is Just-in-Time provisioning and how to set it up](https://support.atlassian.com/atlassian-cloud/kb/what-is-just-in-time-provisioning-and-how-to-set-it-up/)
- [Understand user provisioning](https://support.atlassian.com/provisioning-users/docs/understand-user-provisioning/)

### ADE implications

- Keep JIT as an admin-selectable fallback, not the only enterprise path.
- Offer explicit provisioning mode selection to avoid ambiguous behavior.

## Cross-Vendor Convergence (What to copy)

1. SCIM endpoints should be standards-shaped (`/scim/v2/...`) and predictable.
2. Provisioning ownership should be explicit per tenant/org.
3. Group membership updates should not silently provision unknown users.
4. Deprovision should map to account disable/inactive semantics, not silent hard-delete.
5. Audit logs must distinguish actor/channel (`admin`, `jit`, `scim`).

## Recommendation Input to ADE

1. Support three provisioning modes: `disabled`, `jit`, `scim`.
2. In JIT mode, hydrate group membership at sign-in for that user only.
3. In SCIM mode, accept inbound provisioning/group updates and remove dependence on background directory polling.
4. Preserve invitations as explicit provisioning path independent of JIT/SCIM.
