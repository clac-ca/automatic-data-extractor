# Add ade CLI wrapper

Owner: jkropp
Status: done
Created: 2025-10-20T02:00:14.280Z

---
- 2025-10-20T02:00:18.054Z • jkropp: starting ade CLI wrapper work
- 2025-10-20T02:01:22.857Z • jkropp: added ade CLI wrapper scripts and docs
- 2025-10-20T02:03:38.916Z • jkropp: doc tweak: ade wrapper requires only npm install + npx
- 2025-10-20T02:06:25.967Z • jkropp: user hit existing python ade command; remind to use npx or alias
- 2025-10-20T02:08:30.758Z • jkropp: removed legacy python ade shim and installed wrapper in ~/.local/bin
- 2025-10-20T02:12:05.569Z • jkropp: README + AGENTS.md now reference ade alias
- 2025-10-20T02:14:21.443Z • jkropp: ade now reads descriptions/order from package.json and help output improved
- 2025-10-20T02:15:03.927Z • jkropp: Docs reverted to npm run focus; README mentions optional ade alias
- 2025-10-20T02:17:29.204Z • jkropp: restored ade alias (simple) and removed package.json metadata
- 2025-10-20T02:19:16.009Z • jkropp: Shipped minimal ade alias (binary + simple help). Docs highlight npm run first.
