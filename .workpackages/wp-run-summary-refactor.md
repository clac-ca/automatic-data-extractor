---

> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for the run summary refactor.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Finalize and document the **summary schema** for `run/file/sheet/table` (names, structure, semantics)
* [x] Implement **Pydantic (or equivalent) models** for the 4 summary levels + shared substructures
* [x] Implement **engine-side summary aggregation** (from table-level facts → sheet/file/run summaries)
* [x] Emit `engine.table.summary`, `engine.sheet.summary`, `engine.file.summary`, `engine.run.summary` events with the new payloads
* [x] Update ade-api to **persist `engine.run.summary`** payload on the `runs` row and stop recomputing summaries from events
* [x] Update tests and docs, including any **reporting/telemetry documentation** to reflect the new schema and naming

---

## Scope & Design Notes

* No backward compatibility is required; replace `RunSummaryV1` with a hierarchical summary schema.
* Four scopes share a consistent shape (`counts`, `fields`, `columns`, `validation`, `details`), with scoped `source` metadata and `parent_ids`.
* Counts emphasize raw facts (rows, columns, fields, distinct headers, mapped/unmapped/empty). Percentages are intentionally omitted.
* Field summaries:
  * Table scope: `field`, `label`, `required`, `mapped`, `score`, `source_column_index`, `header`.
  * Aggregate scopes: `mapped` (at least once in scope), `max_score`, plus counts of where it mapped (`tables_mapped`, `sheets_mapped`, `files_mapped`).
* Column summaries:
  * Table scope describes physical columns (header, emptiness, mapped field info, score, output header).
  * Aggregate scopes track distinct headers with occurrence counts and mapped field tallies.
* Validation summaries capture counts by severity/code/field, total issues, rows evaluated, and `max_severity`.
* Engine owns aggregation:
  * Emit `engine.table.summary`, then aggregate to sheet/file/run.
  * Emit `engine.sheet.summary`, `engine.file.summary`, and final `engine.run.summary`.
* ade-api should persist `engine.run.summary` directly on the run row instead of recomputing from event logs; the stored summary is authoritative for UI/API responses.
* Documentation must describe the new schema and event payloads; tests should cover aggregation and API persistence.
