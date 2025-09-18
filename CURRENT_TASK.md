# Current Task — Document retention and deletion plan

## Goal
Design the retention policy and deletion workflow for stored documents so operators can manage disk usage beyond the upload
size cap.

## Background
- Upload size enforcement now protects the system from runaway single requests, but documents accumulate indefinitely.
- Operations teams have asked for guidance on how long to retain uploaded files and how to purge them when storage becomes
  constrained.
- Deletion flows must preserve auditability for jobs that referenced a document while allowing compliant removal of the
  underlying file when permitted.

## Scope
- Document the desired retention period(s) for uploaded documents, including any grace windows tied to job lifecycles.
- Propose API surface and permissions for deleting a document (e.g., `DELETE /documents/{document_id}`) while keeping metadata
  for audit trails.
- Identify background cleanup tasks or scheduled jobs needed to enforce retention automatically.
- Call out schema or storage changes required to track deletion state (timestamps, soft-delete markers, audit logs).
- Enumerate risks and mitigations (e.g., deleting a document that still feeds a pending job, regulatory requirements for
  retention).

## Deliverables
1. Retention policy draft covering default duration, overrides, and operator responsibilities.
2. Deletion workflow design (API contract, auth model, storage interactions, audit logging expectations).
3. Implementation outline split into incremental engineering tasks ready for execution.
4. Updated docs/notes pointing to the retention strategy so future work can begin immediately.

## Definition of done
- Stakeholders have an agreed-upon retention approach documented in the repo.
- The proposed deletion API covers validation, authorisation, and audit logging considerations.
- Follow-up engineering tasks are enumerated with clear acceptance criteria.
- Open questions or dependencies (e.g., legal review, storage metrics) are listed for tracking.
