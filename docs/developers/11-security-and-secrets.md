# Security & Secrets

Treat secrets as toxic. Keep ciphertext in manifests and decrypt only inside isolated processes. Never return or log plaintext secrets. Network access is off by default and should be enabled only when necessary.

## Secrets model
Secrets are encrypted in the manifest and stored as ciphertext at rest. They are decrypted only inside the child process and are never returned by APIs.

## Redaction
Never log plaintext secret values. Prefer structured codes and avoid echoing values in exceptions.

## Integrity
Use package hashing (for example, `package_sha256`) for auditing and provenance.

## Network defaults
Network access is off unless explicitly enabled for a call.

## What to read next
Read `02-design-decisions/dd-0001-file-backed-configs.md` for the rationale behind file‑backed configs.
