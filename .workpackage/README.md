Workpackage Basics

Why it exists
- Keep tiny, durable records of ongoing work so agents can rejoin a thread instantly.

What lives here
- `.workpackage/packages/index.json` – master list
- `.workpackage/packages/<id>-<slug>/workpackage.json` – current snapshot
- `.workpackage/packages/<id>-<slug>/notes.md` – running notes
- `.workpackage/packages/<id>-<slug>/log.ndjson` – append-only events

Statuses
- `draft` → idea parked
- `active` → in flight
- `blocked` → waiting on something
- `done` → complete
- `dropped` → no longer pursuing

Everyday loop
1. Create: `npm run workpackage create -- --title "Fix login" --summary "what good looks like"`
2. Mark status: `npm run workpackage status <ref> -- --to active`
3. Drop a note when you touch it: `npm run workpackage note <ref> -- --text "shipped backend"`
4. Show state anytime: `npm run workpackage show <ref>`
5. Watch activity live: `npm run workpackage tail <ref>` (streams `log.ndjson`).
6. Retire one safely: `npm run workpackage delete <ref> -- --yes` (explicit confirmation required).

Power tips
- `<ref>` can be the number (`2`) or slug (`fix-login`).
- `notes.md` is freeform scratch space.
- Logs are JSON lines so other agents can diff or replay context fast.
- Commands return an agent-friendly envelope by default (timestamp, duration, exitCode, payload) with pretty JSON formatting.
- Add `--plain` if you need the raw payload, or `--no-exit` to suppress non-zero exits on `ok: false`.
- Use `npm run workpackage list -- --active` (or `--status draft,blocked`) to see who’s in-flight. Each entry includes a short description from the summary plus per-status counts for fast scanning.
- Need fast discovery? Try `npm run workpackage find "<text>"` or snapshot a mini-kanban with `npm run workpackage board`.
- Destructive reset: `npm run workpackage clear` asks for a `yes` confirmation before removing every package.

- Writes are crash-safe: index and package updates use atomic temp files plus a coarse `.lock` so agents don’t stomp on each other.
