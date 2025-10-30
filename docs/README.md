# ADE Documentation Hub

Welcome to the ADE (Automatic Data Extractor) docs. ADE turns messy spreadsheets into clean, normalized workbooks through a configurable, multi‑pass pipeline.
We’re publishing the docs incrementally, starting with the **Developer** experience.

## Start here

* **[Developer Docs](developers/README.md)** — how ADE processes spreadsheets, how jobs run, and how to configure behavior with code.

## Documentation structure

We organize the docs by audience so you can jump straight to what you need.

* **Developer guide** — building configs, understanding the pipeline, and reading artifacts.

  * Start with: **[Config Packages — Behavior as Code](developers/01-config-packages.md)**
  * Then: **[Job Orchestration — How ADE Runs a File](developers/02-job-orchestration.md)**
  * Reference: **[Glossary](developers/glossary.md)**

* **User guide** *(coming soon)* — frontend walkthrough: uploading files, monitoring jobs, reviewing results.

* **Admin guide** *(coming soon)* — installation, configuration, security, and operational runbooks.

* **API guide** *(coming soon)* — HTTP API reference for integrating ADE into other systems.

> If something is missing or unclear, please open an issue or PR. Your feedback shapes the docs roadmap.

---

# Developer Documentation Style Guide

Use this guide when contributing or reviewing developer docs. Consistent voice, structure, and formatting make the docs easier to read and maintain.

## Voice and tone

Write like a helpful peer explaining how to get something done.

* Use **second person** (“you”) and **active voice**: “Configure the environment,” not “We will configure…”
* Keep it **direct and friendly** without slang or jokes. Avoid calling tasks “simple” or “easy.”
* Prefer clear verbs (“click” over “hit”) and concrete language.

**Not recommended:** “Let’s now configure the environment for our app.”
**Recommended:** “Configure the environment for your app.”

## Language and grammar

* Use **standard American English** and **present tense** for facts and procedures.
* Keep sentences short. One idea per sentence when possible.
* Put **conditions before instructions**: “If you haven’t installed the CLI, install it now.”
* Spell out acronyms on first use unless universally known (HTTP, JSON).
* Link the first mention of defined terms to the **[glossary](developers/glossary.md)**.

## Structure and formatting

### Titles and headings

* One H1 per page (Title Case).
* Subsequent headings use **sentence case** and follow a logical hierarchy.
* Begin each section with a short intro paragraph (3–5 sentences).

### Lists

* Use bullet lists for unordered items; numbered lists for steps.
* Keep list items parallel (all verbs or all noun phrases).
* Use the **Oxford comma** in series of three or more items.

### Emphasis and code

* **Bold** UI labels and menu items.
* Use `code font` for filenames, commands, API paths, config keys, and literals.
* Keep *italics* rare and purposeful.

### Dates and times

* Prefer explicit dates: “February 10, 2025” and include time zones when relevant (“5:00 PM UTC”).
* Avoid time‑relative phrasing (“currently,” “today”).

## Links and cross‑references

* Use descriptive link text (“See **Config Packages**”) rather than “click here.”
* Use **relative links** for internal pages.
* Link a term’s **first occurrence** on a page to the glossary or its reference page.

## Code samples and snippets

Introduce every snippet with a short sentence that explains what it shows, then follow with a fenced code block. Keep examples realistic and minimal (≤30 lines).

* Use language hints (` ```python `, ` ```bash `) for highlighting.
* Omit boilerplate; use inline comments to indicate omitted sections (`# ...`).
* Use clear placeholders like `<PROJECT_ID>` and never include secrets.

**Example:**

```yaml
apiVersion: v1
kind: Configuration
metadata:
  name: sample
  # ...
spec:
  setting: "value"
```

## Figures and media

Use images only when they genuinely help. Prefer text diagrams (ASCII) when possible.
If you include images, add concise alt text, introduce them in the prose, and use high‑quality assets (SVG for diagrams, PNG for UI). Avoid exposing real data.

## Accessibility and inclusivity

* Provide alt text, logical heading structure, and accessible Markdown.
* Do not rely on color alone to convey meaning.
* Use inclusive language and neutral examples.

## Review checklist

Before merging a doc change:

* Is the title accurate and the intro clear?
* Do sections follow a logical order with short openings?
* Are voice and tone consistent (second person, active voice)?
* Are links, filenames, and code fences correct?
* Do examples avoid secrets and unnecessary complexity?

## References

* Google developer documentation style guide — highlights
* Voice and tone
* Inclusive documentation
* Writing for a global audience
* Headings and titles
* Code samples

*(Use the canonical Google resources; keep this list for orientation, not strict citation.)*

---

## Contribute and get help

* For content issues or gaps, **open an issue** with a clear title and a short summary of the problem.
* For fixes, **open a pull request**. Follow the style guide above and reference impacted pages.
* For roadmap questions or priorities, add a comment to the issue or PR explaining the use case.

---

## Changelog

Track major documentation updates here (optional). If you maintain a separate CHANGELOG, link it from this section.

* *2025‑10‑30:* Initial pass at the hub structure; added style guide; clarified developer entry points.

---

## What’s next

Go to the **[Developer Docs](developers/README.md)** and begin with:

1. **[Config Packages — Behavior as Code](developers/01-config-packages.md)**
2. **[Job Orchestration — How ADE Runs a File](developers/02-job-orchestration.md)**
3. **[Glossary](developers/glossary.md)**

As new sections (User, Admin, API) go live, we’ll link them from the “Documentation structure” section above.