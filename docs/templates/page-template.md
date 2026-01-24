# Page Template

Use this template to create any new documentation page. It encodes our standard structure (Audience/Goal, At a glance, Minimal example, and What’s next) and can be adapted for tutorials, how‑tos, explanations, and references.

## Title and introduction

### <Page Title (Title Case)>

**Audience:** <who should read this>  
**Goal:** <what readers can do or understand after this page>

> **At a glance**
>
> - One‑line summary of the concept or task.
> - One‑line outcome the reader achieves.
> - Optional tiny diagram or list (≤ 5 bullets).

Introduce the topic in 1–3 sentences. State context and constraints briefly. If there are several prerequisites, list them in “Before you begin.”

## Before you begin

- <roles/permissions, versions, prerequisites, inputs>
- <links to setup pages or earlier concepts>

---

## Section 1: Descriptive section heading (sentence case)

(Use this section to start the main content. For task‑oriented docs, use an action phrase like “Configure the environment”; for conceptual docs, use a noun phrase like “Overview of the runtime model”.)

Open with brief background or the first task. Introduce code with a sentence and a colon:

```bash
bash scripts/dev/setup.sh
ade dev
```

If steps are required, use a numbered list:

1. Step description — Explain the action.
2. Next step — Provide the next action with enough detail.
3. Sub‑step or note — Add tips or cautions only when necessary.

## Section 2: Another relevant heading

Add additional sections as needed. Start each with a short intro, then instructions, examples, or reference details.

### Subsection (if needed)

Use subsections sparingly to keep hierarchy clear. Avoid nesting beyond H3 unless required.

---

## Minimal example

Provide a minimal, copy‑pasteable example (≤ 30 lines). Use realistic placeholders and add a one‑line caption. Follow `./snippet-conventions.md` for formatting.

```python
# Example: Transform a column of Member IDs (uppercase)
ids = ["a123", "a124", None, "a125"]
normalized = [s.upper() if isinstance(s, str) else None for s in ids]
print(normalized)  # ['A123', 'A124', None, 'A125']
```

> Note: If examples exceed 30 lines, link to a file in `templates/` or `examples/`.

---

## Notes & pitfalls

- <edge case 1 and how to avoid it>
- <edge case 2>

> Warning: <the one “footgun” to avoid>

## What’s next

- Next: <Link to the next logical page>
- Reference: <Link to a reference page>
- Troubleshooting: <Link to a related guide>
- Verify locally: consider `ade test`, `pytest -q`, or `alembic upgrade head`

---

## Changelog

- YYYY‑MM‑DD — <what changed>

---

## Review checklist (delete before publishing)

- Voice: second person, imperative, active, present tense
- Avoids “simple,” “easy,” “just,” “obviously,” and similar fillers
- Headings: Title Case (H1) and sentence case (H2+); list items parallel
- First occurrence of defined terms links to `../12-glossary.md`
- Minimal example ≤ 30 lines; placeholders are clear; snippet conventions applied
- Links are descriptive and relative; no secrets in code or text
- Accessibility: heading order, alt text for images if any, tables/code render well
