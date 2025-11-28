No behavioural changes are required here; the existing router already uses AuthService and AuthenticatedIdentity in a clean way.

The only indirect change is that AuthService is now delegating to sub‑services internally, and dev identity is no longer hammering the DB on every request when auth_disabled is on.

You can keep your current router.py unchanged.