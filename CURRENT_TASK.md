# 📋 AI Agent Prompt — Simplify Identifiers, Storage, and Logs

> **Context**  
> This is a **small internal line-of-business app**.  
> Prioritize **simplicity, clarity, and maintainability** over clever abstractions or scale.  
> Public behavior should remain stable unless the change clearly improves correctness or developer experience with low risk.

---

## Your Task
Refactor the codebase to simplify how identifiers, file storage, and audit logs are handled.

### 1. Identifiers
- Replace ULID (`ulid.new()`) with UUIDv4 for `document_id`.  
- Use the standard Python `uuid` library.  
- Ensure all ORM defaults, schemas, and tests expect UUIDs instead of ULIDs.  

### 2. File Storage
- Remove the `secrets.token_hex` random tokens and two-level directory scheme (`ab/cd/token`).  
- Instead:  
  - Store uploaded files under `var/documents/uploads/`  
  - Store processed/derived files under `var/documents/output/`  
  - Use the document’s UUID as the file name.  
- Eliminate `resolve_document_path` complexity — paths should be directly predictable.

### 3. Audit Logs → Events
- Rename all `audit_events` references to `events`:  
  - API endpoints (`/events`)  
  - ORM models and tables (`Event`)  
  - Service layer (`events.py`)  
  - Tests, docs, AGENTS.md, README.md  
- Ensure consistency across naming and migration scripts.  
- This keeps the door open for a future `audit_log` feature built on top of `events`.

### 4. System Logs
- Keep system logs as structured logging to stdout/stderr in real time (e.g., via `logging`).  
- Do **not** persist system logs to SQL. They’re operational only.  
- Continue writing to the new `events` table **only for audit/user actions**.

---

## Deliverables
- Updated models, migrations, and services for UUID-based IDs.  
- Simplified storage backend using UUID-based filenames in two directories (`uploads/`, `output/`).  
- Full rename of `audit_events` → `events` across code, migrations, and docs.  
- Removal of two-level storage and redundant token logic.  
- Logging setup consistent with separation of concerns:
  - `events` = audit/user actions (SQL table)  
  - `logging` = system/runtime events (stdout/stderr)  

---

## Principles
- **Clarity first**: choose the least surprising implementation.  
- **Consistency**: align identifiers, paths, and naming across modules.  
- **Maintainability**: reduce custom helpers in favor of stdlib.  
- **Minimalism**: keep only what is necessary for the LoB use case.
