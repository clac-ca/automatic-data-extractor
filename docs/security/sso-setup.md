---
Audience: Platform administrators
Goal: Configure and verify ADE's OpenID Connect single sign-on integration.
Prerequisites: Admin access to the identity provider, the ADE deployment URL, and the ability to restart ADE.
When to use: Enable SSO for the first time, rotate client secrets, or troubleshoot login issues.
Validation: `/auth/sso/login` redirects to the provider, `/auth/sso/callback` returns an ADE token, and new users are auto-provisioned when `email_verified` is true.
Escalate to: Platform owner if the provider lacks the required scopes or cannot issue RS256 ID tokens.
---

# SSO setup

ADE implements a textbook OIDC authorisation-code flow with PKCE. The API caches the provider discovery document and JWKS keys,
performs nonce validation, and issues a standard ADE JWT after successful logins. Follow the steps below to enable the
integration.

## 1. Gather provider details

Collect the following values from your identity platform:

- **Client ID and secret** – register ADE as a confidential web application and record the generated credentials.
- **Redirect URI** – add `https://<ade-host>/auth/sso/callback` (or `http://localhost:8000/auth/sso/callback` for local testing).
- **Issuer URL** – the root URL that exposes `/.well-known/openid-configuration`.
- **Scopes** – ADE expects at least `openid` and `email`. Include `profile` if the provider requires it to expose `email_verified`.
- **Resource audience (optional)** – some providers require a dedicated audience/resource parameter when exchanging the code. If
  unused, leave `ADE_SSO_RESOURCE_AUDIENCE` unset.

## 2. Configure ADE

Set the environment variables before restarting ADE:

```bash
export ADE_SSO_CLIENT_ID="<client-id>"
export ADE_SSO_CLIENT_SECRET="<client-secret>"
export ADE_SSO_ISSUER="https://login.example.com/"
export ADE_SSO_REDIRECT_URL="https://ade.example.com/auth/sso/callback"
export ADE_SSO_SCOPE="openid email profile"
# Optional audience claim enforced on access tokens
# export ADE_SSO_RESOURCE_AUDIENCE="api://ade"
```

Ensure `ADE_JWT_SECRET_KEY` is also set; the same key signs the state cookie and ADE's own access tokens.

## 3. Validate the flow

1. Restart ADE so the new settings take effect.
2. Open `/auth/sso/login` in a browser. ADE should redirect to the provider.
3. Authenticate with a test account that has `email_verified=true`.
4. After the provider redirects back to `/auth/sso/callback`, ADE returns `{ "access_token": "...", "token_type": "bearer" }`.
5. Send the returned token to `/auth/me` to verify the mapped user and role.

ADE creates a new user automatically when the provider supplies a verified email address that does not already exist in the
`users` table. The canonicalised form stored in `users.email_canonical` ensures future logins match even if the provider changes
letter casing or Unicode composition. Accounts inherit the default `viewer` role; adjust the role manually via the CLI if
elevated permissions are required.

## 4. Troubleshooting tips

- **400 Invalid token response** – confirm the provider is issuing RS256 ID tokens and that the configured scopes include `email`.
- **State mismatch errors** – clear browser cookies for the ADE domain to remove stale `ade_sso_state` values.
- **Access token audience failures** – either set `ADE_SSO_RESOURCE_AUDIENCE` to the expected value or unset it when the provider
  does not return an audience claim.
- **Auto-provisioning skipped** – the provider must include `email_verified: true`. If that is not available, pre-create the user
  via the CLI and map the SSO subject manually.

Once SSO is stable, keep the CLI credentials in reserve for break-glass access and rotate the client secret according to your
organisation's standard cadence.
