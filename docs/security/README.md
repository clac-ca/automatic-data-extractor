---
Audience: Platform administrators, IT architects, Security teams
Goal: Explain ADE's authentication options and security controls, and route readers to setup and recovery procedures.
Prerequisites: Access to ADE configuration, environment variable management, and identity provider credentials when SSO is enabled.
When to use: Visit when selecting an authentication mode, configuring SSO, or auditing access controls.
Validation: Ensure both authentication guides render and reference the correct backend modules; capture TODOs for upcoming runbooks.
Escalate to: Security lead or platform owner if authentication behaviour diverges from the documented modes.
---

# Security

ADE ships with deterministic authentication logic and lightweight account management. Use this section to choose the correct mode for your deployment and to maintain SSO integrations.

## Available guides

- [Authentication modes](./authentication-modes.md) — overview of password logins, OIDC SSO, and API keys with environment variables.
- [SSO login quick start](./sso-login.md) — walk through the redirect flow, PKCE state handling, and troubleshooting tips.
- [API key management](./api-keys.md) — issue, rotate, revoke, and audit automation credentials.
- [SSO setup and recovery](./sso-setup.md) — configure discovery, callbacks, and JWKS caching behaviour; covers validation and recovery steps.

## Planned runbooks (TODO)

- `sso-outage-recovery.md` — diagnose redirect errors, invalid tokens, and cache resets.
- `admin-access-recovery.md` — restore platform access when all administrators are locked out.
