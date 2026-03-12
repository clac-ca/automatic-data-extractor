## Summary

What does this change do and why?

## Changes

- 
- 

## How to test

Steps to verify locally and/or in CI:

- [ ] `ade ci` (or relevant subset)
- [ ] `docker build .` (if Docker changes)
- [ ] `docker compose -f docker-compose.yaml up` (if dev stack changes)

## Screenshots / recordings (if UI)

Add before/after screenshots or a short recording if this touches **ade-web**.

## Checklist

- [ ] I linked the relevant issue(s) (or explained why none are needed).
- [ ] I added/updated tests where it makes sense.
- [ ] I updated docs / README if behavior or configuration changed.
- [ ] I considered backwards compatibility / migration impact.
- [ ] I verified environment variables use the `ADE_` prefix.
- [ ] I verified this change doesn’t break devcontainer onboarding.

## Notes for reviewers

Anything that would help a reviewer (risk areas, follow-ups, rollout plan, etc.).

## Release metadata for `development` -> `main` promotions

If this PR promotes `development` into `main` and will be squash-merged, add either:

- a releasable Conventional Commit title such as `fix: ...`, `feat: ...`, or `deps: ...`
- a Release Please override block in the PR body

Example:

```text
BEGIN_COMMIT_OVERRIDE
# Add one releasable conventional line per user-facing change, for example:
# feat(documents): redesign activity threads (#329)
# fix(api): stabilize release metadata handling (#333)
END_COMMIT_OVERRIDE
```
