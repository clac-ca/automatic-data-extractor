---
Audience: Platform administrators, Automation engineers
Goal: Explain how to issue, use, and revoke ADE API keys without leaking the secret material.
Prerequisites: Administrator access to ADE (CLI or API) and an understanding of the systems that will store the API key.
When to use: Provisioning automation credentials, rotating existing keys, or auditing recent API key activity.
Validation: `POST /auth/api-keys` returns a raw key, `GET /auth/api-keys` lists metadata with last-seen timestamps, and revoked keys no longer authenticate.
Escalate to: Security team if a key is exposed or automation cannot authenticate after rotation.
---

# API key management

API keys provide non-interactive access to ADE's REST API. Each key is scoped to a user account, hashed at rest, and validated in constant time. Use the steps below to issue keys, distribute them safely, and review usage.

## 1. Issue a key

API keys contain a short prefix and a random secret separated by a dot (`prefix.secret`). ADE stores only the prefix and a salted SHA-256 hash of the secret.

```bash
# CLI
python -m backend.app auth create-api-key analyst@example.com --expires-in-days 30

# HTTP (requires admin bearer token)
curl -X POST https://ade.example.com/auth/api-keys \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst@example.com", "expires_in_days": 30}'
```

Copy the returned key once and store it in your secret manager. Treat it like a password—ADE cannot recover the secret after creation.

## 2. Authenticate with the key

Clients send the raw key in the `X-API-Key` header. ADE matches on the prefix, compares the hashed secret, and (at most once per configured interval) updates the `last_seen_at`, `last_seen_ip`, and `last_seen_user_agent` fields.

```bash
curl https://ade.example.com/documents \
  -H "X-API-Key: ab12cd34.N6b1PX2U2pK2H1wAajy-dJ0gi8o"
```

## 3. Review active keys

Administrators can list issued keys and inspect last-seen metadata via API or CLI. The response includes the ULID, owner, prefix, optional expiry, and most recent activity.

```bash
# HTTP
curl https://ade.example.com/auth/api-keys \
  -H "Authorization: Bearer <admin-token>"

# CLI
python -m backend.app auth list-api-keys
```

Use the prefix to match secrets in downstream systems without exposing the full key.

## 4. Revoke or rotate

To revoke a key immediately, delete it via the API or CLI. ADE removes the stored hash so the raw key can no longer authenticate, and records `auth.api_key.revoked` events for audit trails.

```bash
# HTTP
curl -X DELETE https://ade.example.com/auth/api-keys/<api_key_id> \
  -H "Authorization: Bearer <admin-token>"

# CLI
python -m backend.app auth revoke-api-key 01HX4E4N5S9YJ3SM6C3H9XQZ2T
```

When rotating, create the replacement key first, update dependent systems, and then revoke the old key.

## 5. Audit activity

Every creation and revocation emits structured events with the key's prefix, owner, and actor metadata. Query `/events?event_type=auth.api_key.created` (or `auth.api_key.revoked`) to review issuance history, or subscribe to the event feed for alerting.
