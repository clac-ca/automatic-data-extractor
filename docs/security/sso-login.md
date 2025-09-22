---
Audience: Platform administrators, Support engineers
Goal: Provide a concise SSO login walkthrough that operators can follow without deep OIDC knowledge.
Prerequisites: Access to the identity provider, ability to configure ADE environment variables, and a browser to validate redirects.
When to use: Enabling SSO for the first time, verifying redirects during incident response, or coaching end users through the flow.
Validation: `/auth/sso/login` redirects to the configured issuer and `/auth/sso/callback` returns an ADE access token for verified users.
Escalate to: Identity team if the provider omits required claims or refuses the configured redirect URI.
---

# SSO login quick start

ADE implements the standard OIDC authorisation-code flow with PKCE. Once configured, the ADE backend exchanges the provider's `id_token` and `access_token` for its own bearer token so the UI and API clients behave consistently. Use this guide to wire the flow end-to-end and troubleshoot the common failure points.

## 1. Configure the identity provider

1. Register ADE as a confidential web application.
2. Record the **client ID** and **client secret** that the provider generates.
3. Add the redirect URI `https://<ade-host>/auth/sso/callback` (or the equivalent `http://localhost:8000/...` for local testing).
4. Ensure the client can request the `openid`, `email`, and `profile` scopes and returns verified email addresses.

## 2. Set ADE environment variables

```bash
export ADE_SSO_CLIENT_ID="<client-id>"
export ADE_SSO_CLIENT_SECRET="<client-secret>"
export ADE_SSO_ISSUER="https://login.example.com"
export ADE_SSO_REDIRECT_URL="https://ade.example.com/auth/sso/callback"
export ADE_SSO_SCOPE="openid email profile"
# Optional: require an audience on provider access tokens
# export ADE_SSO_RESOURCE_AUDIENCE="api://ade"
```

Restart ADE so the new settings take effect. The backend caches the discovery document and JWKS keys, so routine logins do not hammer the identity provider.

## 3. Walk through the flow

1. Browse to `/auth/sso/login`. ADE fetches the discovery metadata (once), generates a PKCE verifier, and sets a signed `ade_sso_state` cookie.
2. After the redirect, authenticate with a user whose email address is verified by the provider.
3. The provider calls back to `/auth/sso/callback` with the code and state. ADE validates the state cookie, verifies the ID token via JWKS, and issues its own bearer token in the JSON response.
4. Call `/auth/me` with the returned `Authorization: Bearer <token>` header to confirm the resolved ADE user and role.

## 4. Troubleshoot common issues

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `400 Missing authorization code or state` | The provider removed parameters or the callback URL is incorrect. | Confirm the redirect URI exactly matches the registered value. |
| `400 State mismatch` | The `ade_sso_state` cookie is missing or stale. | Clear cookies for the ADE domain and restart the flow. |
| `400 Invalid token response from identity provider` | The provider did not return `id_token`, `access_token`, or `token_type=Bearer`. | Enable the standard OIDC scopes and ensure the client is authorised for them. |
| `400 Identity provider response missing required claims` | The ID token lacked `email` or `sub`. | Configure the provider to include a verified email claim or pre-provision the user and map the subject manually. |
| `502 Unable to contact identity provider` | Network or configuration issue fetching the discovery document/token endpoint. | Validate the issuer URL and check network access between ADE and the IdP. |

Successful and failed login attempts emit `auth.sso.login.succeeded` and `auth.sso.login.failed` events. Use `/events` to audit who signed in and why a callback failed during incident response.
