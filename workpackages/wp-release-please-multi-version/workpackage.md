# Work Package: Release Please multi-version + single image version

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Implement Release Please in manifest mode so ADE has independent component versions for api/web/worker plus a single root image version, using standard tag conventions and minimal complexity. Add configuration, workflow wiring, version files, and documentation so releases are predictable and CI-compatible on the `development` branch.

### Scope

- In:
  - Add root image version source of truth (root `VERSION`) and align Docker tagging.
  - Configure Release Please manifest mode for `ade-api`, `ade-web`, `ade-worker`, and root image.
  - Standard tag naming: `vX.Y.Z` for image; `ade-api-vX.Y.Z`, `ade-web-vX.Y.Z`, `ade-worker-vX.Y.Z` for components.
  - Update release workflow(s), docs, and examples to reflect the new release flow.
- Out:
  - Publishing to package registries (PyPI/NPM).
  - Any custom release tooling beyond Release Please.

### Work Breakdown Structure (WBS)

1.0 Design + config decisions
  1.1 Confirm version sources and tag naming
    - [x] Define root image version file location (`VERSION`) and format.
    - [x] Confirm component version files (api/worker `pyproject.toml`, web `package.json`).
    - [x] Lock tag conventions for image and components.
  1.2 Release Please mode
    - [x] Choose manifest mode (multi-package) with root package for image.
    - [x] Decide changelog locations (root + per-component or per-component only).

2.0 Release Please configuration
  2.1 Add config files
    - [x] Create `release-please-config.json` with package definitions and paths.
    - [x] Create `.release-please-manifest.json` with initial versions.
  2.2 Workflow wiring
    - [x] Add/update `release-please` workflow targeting `development`.
    - [x] Ensure permissions and token handling are standard and minimal.

3.0 Docker tagging alignment
  3.1 Image version integration
    - [x] Ensure image tags use `vX.Y.Z` from Release Please tags.
    - [x] Confirm `latest` behavior (release tags only).

4.0 Documentation + validation
  4.1 Docs
    - [x] Update README/docs to describe multi-version releases and image version.
    - [x] Document release flow and tag mapping.
  4.2 Validation
    - [x] Validate config structure and example release PR contents.
    - [x] Confirm workflows trigger on `development` and tags.

### Open Questions

- Root changelog: yes. Use a root `CHANGELOG.md` for the image/bundle; per-component changelogs are skipped.
- Initial root image version: `1.6.5`, aligned to the current API version.
- Root image version bumps on any change (no path exclusions to keep the flow simple).

---

## Acceptance Criteria

- Release Please runs on `development` and opens a single PR that bumps only the impacted component versions plus the root image version.
- Tags produced on merge follow the agreed convention: `vX.Y.Z` for image and `ade-*-vX.Y.Z` for components.
- Docker workflow publishes image tags for releases based on the root version tag, with `latest` only on release tags.
- Docs explain the release workflow, version sources, and tag mapping clearly.

---

## Definition of Done

- All WBS tasks are checked off.
- Workflow changes are linted/validated where possible.
- No extra tooling or bespoke scripts beyond Release Please configuration.
- Documentation is updated and accurate.
