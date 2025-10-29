# DD-0004: Manifest Secrets Model

Date: 2025-10-29

## Context

Scripts need credentials; we must avoid leaking secrets in code, logs, or APIs.

## Decision

Secrets are stored encrypted in the manifest. They are decrypted only inside the child process environment and never returned by APIs.

## Consequences

- Pros: at‑rest encryption, least‑privilege exposure, safer logs.
- Cons: requires encryption/decryption plumbing and key management.

## Alternatives considered

- Plaintext in environment or files — unacceptable risk.

## Links

- See: `../09-security-and-secrets.md`
