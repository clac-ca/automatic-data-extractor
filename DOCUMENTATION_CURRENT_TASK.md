# Documentation Plan — API key provisioning workflows

## Goal
Equip operators with clear guidance for issuing, revoking, and auditing API keys through the new admin endpoints while reinforcing secure token handling and event visibility.

## Deliverables (execute in order)

1. **Author the API key management guide**

   * Create `docs/security/api-key-management.md` describing the lifecycle (creation, storage expectations, revocation) and include HTTP request/response samples plus curl snippets.
   * Highlight how the raw token is returned once and how to store it securely.
   * Document the events emitted for creation and revocation so audit teams know what to monitor.

2. **Update navigation and references**

   * Link the new guide from `docs/security/README.md` with a short summary.
   * Surface the guide in `docs/README.md` under the security/operations sections so automation owners can find it quickly.

3. **Call out operational safeguards**

   * Note in the operations runbook index (`docs/operations/README.md`) that API key rotation guidance now lives in the security section.
   * Add TODO placeholders for future UI-based key management once designs land.

## Out of scope

* Building UI affordances for API key management.
* Revisiting authentication mode documentation beyond references needed for the new guide.

## Source material

* Newly added API endpoints and Pydantic schemas.
* Existing authentication mode documentation and event log references.
* Backend service helpers for API keys in `backend/app/services/auth.py`.

## Definition of done

* Security docs explain how to create, revoke, and audit API keys using the API.
* Repository navigation points to the new guide from security and operations sections.
* Follow-up TODOs capture UI work without leaving gaps in the interim guidance.
