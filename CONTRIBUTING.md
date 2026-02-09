# Contributing

## Branching
- Default branch: `development`
- Open PRs against `development`
- `main` is stable and updated via `development` merges

## Commit Messages
We use **Conventional Commits**:
- `feat:` new feature (minor)
- `fix:` bug fix (patch)
- `deps:` dependency updates (patch)
- `chore:` internal changes/docs (no release by default)

## Staging Discipline
- Only stage files related to the task
- Avoid bundling unrelated changes

## Testing
- All services (default unit): `ade test`
- Backend (unit): `ade api test`
- Backend (integration/all): `ade api test integration` or `ade api test all`
- Worker (unit): `ade worker test`
- Worker (integration/all): `ade worker test integration` or `ade worker test all`
- Frontend: `npm run test --prefix apps/ade-web`
- Lint (backend): `ade api lint`
- Lint (frontend): `npm run lint --prefix apps/ade-web`

## Releases
- Releases are handled by **Release Please** on `development`
- Do not bump versions manually
- Image version lives in `VERSION`
- Component versions live in each app manifest
- See `docs/releasing.md` for details
