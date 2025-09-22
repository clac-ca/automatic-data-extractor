---
Audience: Platform administrators
Goal: Document the current stance on SSO support.
Prerequisites: None
When to use: Confirm whether ADE integrates with an identity provider.
Validation: n/a
Escalate to: Platform owner if SSO is required in the future.
---

# SSO support

The simplified authentication stack no longer includes an OpenID Connect or Azure AD integration. ADE now relies solely on
first-party email/password credentials and short-lived bearer tokens.

If your organisation requires SSO, capture the requirements as a follow-up task. Reintroducing it would involve wiring a
well-maintained FastAPI dependency rather than rebuilding custom flows.
