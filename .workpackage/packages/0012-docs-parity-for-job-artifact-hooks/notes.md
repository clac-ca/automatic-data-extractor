# Docs parity for job artifact & hooks

Owner: unknown
Status: active
Created: 2025-11-03T15:55:00.815Z

---

## Task checklist

- [x] Implement documented artifact schema
- [ ] Align hook lifecycle with documentation
- [ ] Add per-job requirements.txt installation
- [x] Let column transforms remain optional
- [x] Support unmapped column append + output metadata

## Notes

Initial findings captured in chat. Beginning with optional transform validation adjustments as a quick win before expanding artifact surface.
- 2025-11-03T16:00:39.117Z • unknown: Column transforms are now optional; updated validator + tests.
- 2025-11-03T16:15:44.910Z • unknown: Aligned pipeline + worker artifact output to documented schema with sheets, mapping traces, pass history, and output summary.
- 2025-11-03T16:42:10.000Z • unknown: Added A1 coordinates to validation issues, normalized common codes, refreshed validator messaging, docs, and tests.
- 2025-11-03T17:05:00.000Z • unknown: Trimmed obsolete pass bookkeeping in the worker, expanded engine defaults in artifact snapshots, and clarified transform hints + docs edge-case note.
- 2025-11-03T17:50:00.000Z • unknown: Added per-pass stats, stable rule identifiers, hook annotations, and read-only workbook loading; refreshed docs/tests to reflect the richer artifact shape.
- 2025-11-03T18:10:00.000Z • unknown: Appended unmapped columns in the writer output with column plan metadata, froze hook artifact snapshots before execution, and documented optional data ranges plus annotation timestamps.
- 2025-11-03T18:45:00.000Z • unknown: Fixed missing workbook import, loaded new hook groups with enabled flags, expanded the artifact JSON schema/docs to match emitted fields (annotations, stats, rule refs), and cleaned test noise.
