# AGENTS.md — Developer Docs Authoring Guide

Scope: This file governs all content under `docs/developers/`.
Audience: Humans and agents contributing developer‑focused documentation.

## Goals

- Keep pages short, consistent, and easy to scan.
- Mirror the mental model: config = folder; one active config; multi‑pass jobs.
- Prefer examples and links over long prose.

## Directory Layout & Naming

- 00-templates/ — reusable page and snippet templates (do not publish content here).
- 01-schemas/ — JSON Schemas used by docs; add examples that validate against them.
- 02-design-decisions/ — permanent “DD” files capturing major decisions.
- Top‑level numbered pages (e.g., `01-overview.md`, `05-mapping-format.md`).
- Use two‑digit numeric prefixes to control order; keep existing numbers stable.

## Page Structure (use 00-templates/page-template.md)

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
- Terminology: define in `02-glossary.md` once; link the first occurrence on a page.
- Navigation: every page ends with “Next” and “Previous”.

## Snippet Conventions

- JSON: compact, no trailing commas; comments belong in surrounding prose.
- Python: 3.11+, keyword‑only args; types where they clarify intent.
- File trees: show only relevant parts in `tree` style.

## Cross‑Linking

- Use relative links only (no absolute URLs). Example: `../02-glossary.md`.
- When schemas are relevant, link into `01-schemas/…`.
- Link to DDs under `02-design-decisions/` from the relevant pages.

## Design Decisions (DDs)

- File name: `dd-####-slug.md` (zero‑padded, permanent number; do not renumber).
- Format: Date → Context → Decision → Consequences → Alternatives considered → Links.
- Keep DDs short and stable; supersede with a new DD rather than editing intent.

## Schemas

- Keep JSON Schemas in `01-schemas/` and update references (e.g., `05-mapping-format.md`).
- Provide small validating examples alongside narrative pages where useful.

## Review Checklist (PRs)

- Page follows the template with Audience/Goal and Next/Previous links.
- Examples ≤ 30 lines, use elisions where needed, and match snippet conventions.
- First use of glossary terms links to `02-glossary.md`.
- References to schemas point to `01-schemas/`.
- If introducing/altering a big concept, add or update a DD.

## Coordination

- If work may overlap, use the repo’s work package flow to avoid collisions.
- Keep commits scoped to a single page/topic when possible.
