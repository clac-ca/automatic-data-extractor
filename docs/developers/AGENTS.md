# AGENTS.md — Developer Docs Authoring Guide
Scope: This file governs all content under `docs/developers/`.

## Goals

- Keep pages short, consistent, and easy to scan.
- Mirror the mental model: config = folder; one active config; multi‑pass jobs.
- Prefer examples and links over long prose.

## Directory Layout & Naming

- templates/ — reusable page and snippet templates (do not publish content here).
- schemas/ — JSON Schemas used by docs; add examples that validate against them.
- design-decisions/ — permanent “DD” files capturing major decisions.
- Top‑level numbered pages (e.g., `01-config-packages.md`, `03-mapping-format.md`).
- Use two‑digit numeric prefixes to control order; keep existing numbers stable.

## Page Structure (use templates/page-template.md)

Every page should follow this order:

1) Title
2) Audience & Goal (one line each)
3) Concept (one concise paragraph)
4) Why it matters (short rationale)
5) Minimal example (≤ 30 lines; runnable or copy‑pastable; use elisions)
6) Notes (do/don’t, pitfalls)
7) Next/Previous relative links

Optional: include the “Pipeline at a glance” block where relevant.

## Style Rules

- Voice: concise, direct, non‑marketing.
- One idea per page; split if a second idea creeps in.
- Diagrams: ASCII only, ≤ 80 chars wide, with a short title.
- Code blocks: ≤ 30 lines. Indicate omissions with language‑appropriate comments (for example, `# ...` for Python/YAML/Bash and `// ...` for JS/JSON).
- Do/Don’t boxes: use blockquotes with “Do:” and “Don’t:”.
- Terminology: define in `glossary.md` once; link the first occurrence on a page.
- Navigation: every page ends with “Next” and “Previous”.

## Snippet Conventions

- JSON: compact, no trailing commas; comments belong in surrounding prose.
- Python: 3.11+, keyword‑only args; types where they clarify intent.
- File trees: show only relevant parts in `tree` style.

## Cross‑Linking

- Use relative links only (no absolute URLs). Example: `../glossary.md`.
- When schemas are relevant, link into `schemas/…`.
- Link to DDs under `design-decisions/` from the relevant pages.

## Design Decisions (DDs)

- File name: `dd-####-slug.md` (zero‑padded, permanent number; do not renumber).
- Format: Date → Context → Decision → Consequences → Alternatives considered → Links.
- Keep DDs short and stable; supersede with a new DD rather than editing intent.

## Schemas

- Keep JSON Schemas in `schemas/` and update references (e.g., `03-mapping-format.md`).
- Provide small validating examples alongside narrative pages where useful.

## Review Checklist (PRs)

- Page follows the template with Audience/Goal and Next/Previous links.
- Examples ≤ 30 lines, use elisions where needed, and match snippet conventions.
- First use of glossary terms links to `glossary.md`.
- References to schemas point to `schemas/`.
- If introducing/altering a big concept, add or update a DD.
