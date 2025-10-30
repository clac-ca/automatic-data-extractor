# Design Decisions

This page is the jumping-off point for ADE’s design decision (DD) records. Each DD captures a durable choice that shapes how the system works.

## Audience & goal
- **Audience:** Engineers and product owners needing the “why” behind architecture or workflow choices.
- **Goal:** Find the relevant DD quickly and know when to add a new one.

## When to write a DD
- The change affects multiple components or repos.
- It defines or revises a public contract (API, schema, CLI flag).
- It establishes a new security stance or long-lived invariant.

If you are unsure, err on the side of drafting one. The DD template keeps them short and scannable.

## Directory layout
- Files live in [`design-decisions/`](./design-decisions).
- Naming uses `dd-####-slug.md` (four digits, zero-padded).
- Each file follows the template: Date → Context → Decision → Consequences → Alternatives → Links.

## Workflow
1. Create a new DD file using the next available number.
2. Capture the decision and link to supporting discussions.
3. Reference the DD from the relevant doc pages (or code) so readers see the rationale.

---

Previous: [Shared terminology](./12-glossary.md)  
Next: [Developer overview](./README.md)
