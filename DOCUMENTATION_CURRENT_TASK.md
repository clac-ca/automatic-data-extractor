# Documentation Plan — Simplified Structure & API Key Readiness

## Goal

Produce a clear, durable documentation foundation for ADE. Visualize the architecture and prepare teams for API key rollout, while also simplifying the documentation structure so it is intuitive and easy to navigate.

## Deliverables (execute in order)

1. **Streamline folder structure**

   * Minimize the number of subfolders; avoid deep nesting unless truly necessary.
   * Group related docs by audience and purpose (e.g., `docs/architecture/`, `docs/user/`, `docs/admin/`).
   * Eliminate redundant folders (`docs/foundation/` vs `docs/core/`, etc.)—choose the simplest path that “just makes sense.”

2. **Publish the core architecture diagram**

   * Export the system overview diagram to `docs/architecture/system-overview.png`.
   * Reference it from `docs/architecture/system-overview.md`.
   * Provide an accessibility-friendly text alternative in the same document.

3. **Metadata & ownership**

   * Each asset entry in `docs/README.md` should list its source, last validation date, and owning maintainer.
   * Avoid scattering metadata across multiple README files—consolidate where possible.

4. **Simplify supporting material**

   * Include only what’s essential for understanding workflows, security, and API key upgrades.
   * Use examples (tables, screenshots, CLI snippets) inline with explanations instead of sprawling into multiple files.

## Out of scope

* Automated diagram generation.
* Backend authentication code changes.
* Extended runbooks beyond configuration, storage, security, and API key setup.

## Source material

* Existing `system-overview.md` summary.
* UI prototypes or live screenshots for configuration workflows.
* Security docs for session handling and API key requirements.

## Definition of done

* Navigation is clean and shallow (1–2 levels max).
* New docs include metadata, clear explanations, and inline examples.
* Assets reference validation dates and owners centrally.
