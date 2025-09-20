# Documentation plan: architecture diagrams and API key readiness

## Goal
Produce durable foundation materials that visualise ADE's architecture and give teams a clear upgrade path once API keys are released.

## Deliverables (execute in order)

1. **Publish the core architecture diagram**
   - Export the system overview diagram to `docs/assets/system-overview.png` (or similar) and reference it from `docs/foundation/system-overview.md`.
   - Ensure the asset metadata in `docs/assets/README.md` calls out the source, last validation date, and owning document.
   - Provide an accessibility-friendly text alternative in the system overview document below the embedded image.

2. **Document the configuration UI quick reference**
   - Add `docs/configuration/ui-quick-reference.md` with metadata for configuration managers.
   - Cover the key screens (Drafts, Revisions, Event preview, Smoke test launcher) with short explanations followed by annotated screenshots or tables.
   - Link the new guide from `docs/configuration/README.md` and mention it in the support persona card on `docs/README.md`.

3. **Prepare the API key launch checklist**
   - Create `docs/security/api-keys.md` outlining provisioning, distribution, rotation cadence, and revocation handling.
   - Update `docs/data-integration/api-overview.md` and `docs/reference/environment-variables.md` to replace “roadmap” language with the live feature once available.
   - Add a short announcement blurb to `README.md` summarising how API keys work alongside sessions.

## Out of scope for this iteration
- Automating diagram generation or screenshot capture.
- Changes to backend authentication code.
- Expanding runbooks beyond the configuration and security topics listed above.

## Source material to consult while authoring
- Existing architecture summary in `docs/foundation/system-overview.md`.
- UI prototypes or live instance screenshots covering configuration workflows.
- Security documentation for session handling and future API key requirements.

## Definition of done
- New documents include metadata, clear explanations paired with immediate examples (tables, screenshots, or CLI snippets).
- Navigation updates surface the new guides without TODO placeholders.
- Asset references include validation dates and owners in `docs/assets/README.md`.
- `pytest -q` passes to confirm documentation changes do not break the environment.
