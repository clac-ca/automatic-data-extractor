## `.workpackages/auth-refactor/wp-auth-refactor.md`

```markdown
# Auth refactor work package (split)

The original single file has been split into smaller pieces to make it easier to navigate and apply. The full, unmodified source is preserved at `wp-auth-refactor-full.md`.

## Docs

- `01-overview.md` — intro plus goals/non-goals, context, and checklist.
- `02-high-level-design.md` — service layout, dev-identity plan, and identity/SSO strategy.
- `03-implementation-notes.md` — data model, file responsibilities, micro-level cleanups, and notes about unchanged files.
- `04-benefits.md` — performance, behaviour, and maintainability notes.

## Code listings

The full replacement code from the original section 5 is extracted into real files under `code/` for copy/paste or scripted application:

- `code/apps/ade-api/src/ade_api/features/auth/__init__.py`
- `code/apps/ade-api/src/ade_api/features/auth/models.py`
- `code/apps/ade-api/src/ade_api/features/auth/repository.py`
- `code/apps/ade-api/src/ade_api/features/auth/security.py`
- `code/apps/ade-api/src/ade_api/features/auth/utils.py`
- `code/apps/ade-api/src/ade_api/features/auth/service.py`