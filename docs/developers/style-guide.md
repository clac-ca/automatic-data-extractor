# Developer Documentation Style Guide

This guide defines the voice, tone, and formatting conventions for all developer documentation in this repository. Adhering to a consistent style gives readers a clear, friendly, and helpful experience across every page. These guidelines align with widely adopted technical-writing practices (including Google’s developer documentation style), adapted for our project’s needs.

---

## Voice and tone

Write in a conversational, friendly tone without being frivolous. Sound like a knowledgeable peer guiding the reader through a task. Use **second person (“you”)** to address the reader directly, and rely on the **imperative mood** for instructions. For example, say “Configure the environment for your app” rather than “We will now configure the environment.” Active voice keeps ownership clear: “The system sends an email,” not “An email is sent by the system.”

Keep the voice respectful and inclusive. Avoid slang, colloquialisms, and humor that might not translate globally. Use jargon or buzzwords only when they are standard in the domain; otherwise explain them or choose simpler language. Skip idioms such as “hit it out of the park,” and use neutral phrasing instead. Likewise, avoid ableist or sexist terms—write “give a final check” instead of “give a final sanity check.” Write with a global audience in mind by providing context and choosing clear words.

Keep the tone encouraging and matter-of-fact. It is fine to sound positive, but do not label tasks as “simple” or “easy,” and avoid condescending fillers such as “just,” “obviously,” or “simply.” Use “please” sparingly in instructions (“Click **Submit**,” not “Please click **Submit**”). Reserve “please” for rare cases where it adds clarity or courtesy to narrative text.

Avoid common tone pitfalls: overly cutesy language, unnecessary exclamation marks, repetitive sentence starts (“You can…”), and filler phrases like “Note that…” or “At this time.” Do not use “let’s…” or “we will…” when giving instructions; it is clearer to use “you” or straight imperatives. Do not refer to the docs or product as “we”; focus on the reader’s actions and the software’s behavior.

> **Not recommended:** “Let’s now configure the environment for our app.”  
> **Recommended:** “Configure the environment for your app.”

> **Not recommended:** “Just hit the **Submit** button and you’re good to go!”  
> **Recommended:** “Click **Submit** to send the form.”

Review drafts for tone and clarity. Remove colloquial fillers, pick precise verbs (“click” instead of “hit”), and keep sentences direct.

---

## Language and grammar

- Use **standard American English** spelling and grammar.
- Prefer **present tense** for factual statements and procedural steps. Use future tense only for real future events, and past tense only for historical context or release notes.
- Keep sentences concise. Break up long constructions to improve readability and translation. Each sentence should communicate one idea when possible.
- Use **active voice** so the actor is explicit. Choose passive voice only when the actor is unknown or irrelevant.
- **Put conditions before instructions.** For example, write “If you have not installed the CLI, install it now” instead of “Install the CLI if you have not already done so.”
- Address the reader with **second person pronouns** (“you”). Avoid gendered language (“administrator updates the configuration” instead of “admin updates his configuration”). Use “we” only when the docs must speak for the team or product, and do so sparingly to avoid confusion.
- Spell out abbreviations and acronyms on first use unless they are universally known (for example, HTTP or JSON). Example: “Use the Cloud Execution Manager (CEM) to orchestrate tasks…” Then use the acronym for subsequent mentions.
- If a term appears in the glossary, link its first mention on a page to `docs/developers/glossary.md`. Maintain consistent terminology—do not switch between synonyms for the same concept.

---

## Structure and formatting

### Titles and headings

- Begin every page with a single level-1 heading (H1) that serves as the page title.
- Write page titles in **Title Case**, and write section headings (H2 and below) in **sentence case**.
- Organize headings hierarchically without skipping levels. Ensure each heading reflects its section content.
- Use imperative verbs for task-oriented sections (for example, “Create an instance”). Use noun phrases for conceptual sections (for example, “Architecture overview”).
- Open each major section with a short introductory paragraph so readers know what follows. Aim for paragraphs of roughly three to five sentences to avoid dense walls of text.

### Lists

- Use bulleted lists for items that have no required order, and numbered lists for sequential steps.
- Maintain parallel structure in list items (all verbs, all noun phrases, etc.).
- Capitalize list items consistently. Add end punctuation if any item is a full sentence; otherwise leave punctuation off for fragments.
- Use the **Oxford comma** in any series of three or more items (“Windows, Linux, and macOS”).
- When presenting paired data, consider tables or definition lists.

### Emphasis and formatting

- Use **bold text** for UI elements such as button labels, menu items, and field names (for example, “Click **Deploy**”).
- Use `code font` (backticks) for filenames, commands, API endpoints, config keys, and literal values.
- Reserve *italics* for introducing terms or for rare emphasis.
- When referencing dates, write them in an unambiguous format such as “February 10, 2025.” Include time zones when specifying times (“5:00 PM UTC”).
- Avoid time-sensitive phrases like “today” or “currently.” Write in a timeless style (“In version 3.2 the feature is deprecated”).

---

## Links and cross-references

- Use descriptive link text that explains the destination—avoid “click here” or bare URLs.
- Use relative links for internal references (for example, `[Overview](./README.md)`).
- Link the first mention of defined terms to their glossary or reference page. One link per page is usually sufficient.
- When referencing external resources, use the official name or title as the link text (for example, “See the **TensorFlow documentation**”).
- Periodically verify both internal and external links, especially after restructures or when external resources move.

---

## Code samples and snippets

We maintain detailed snippet guidance in [`docs/developers/templates/snippet-conventions.md`](./templates/snippet-conventions.md). Follow these core principles:

- Introduce each code example with a brief sentence that states what it demonstrates. End the sentence with a colon when it leads directly into the code block.
- Use fenced code blocks with language hints (` ```python `, ` ```bash `, etc.) for syntax highlighting. Keep lines near 80 characters when practical.
- Provide realistic, minimal examples—typically no more than 30 lines, excluding comments.
- Omit irrelevant boilerplate. Use comments that match the language syntax to indicate removed sections (`# ...`, `// ...`). Avoid the Unicode ellipsis character.
- Use clear placeholders for user-specific values, such as `<PROJECT_ID>` or `YOUR_API_KEY`. Never include actual secrets or private data.
- If you need to label an important snippet, introduce it in prose (for example, “**Minimal example:**”).

```yaml
apiVersion: v1
kind: Configuration
metadata:
  name: sample
  # ... (other metadata fields) ...
spec:
  setting: "value"
```

---

## Figures and media

Use diagrams and images only when they genuinely aid understanding. Prefer text-based diagrams (ASCII art) or tables because they are easy to maintain and accessible to screen readers. Keep ASCII diagrams at or below 80 characters in width, and explain them in the surrounding text.

When you must include an image (for example, a UI screenshot or complex architecture diagram), provide concise, meaningful alt text. Use high-quality assets that balance clarity with reasonable file size. Favor SVG for diagrams and PNG for UI screenshots. Introduce images in the prose so readers know to look at them, and add captions when additional context is helpful.

Ensure every media asset respects privacy and security requirements. Scrub identifying data, redact sensitive information, and use representative sample names (for example, “ACME Corp,” “Alice,” “Bob”).

---

## Accessibility and inclusivity

Accessibility is a core requirement. Provide alt text for images, ensure headings form a logical outline, and structure content with proper Markdown syntax so assistive technologies can parse it. Keep contrast requirements in mind when you reference colors or UI states. Avoid describing information solely with color or position; provide textual explanations.

Inclusive language matters. Choose gender-neutral terms, avoid idioms that do not translate well, and ensure examples reflect diverse, respectful scenarios. When in doubt, err on the side of clarity and empathy.

---

## Keep refining

Treat documentation reviews with the same care as code reviews. Read drafts aloud to spot awkward phrasing, confirm that instructions follow the page template in `docs/developers/templates/page-template.md`, and double-check links, examples, and placeholders. Consistent application of this style guide keeps the docs welcoming, precise, and dependable.

---

## References

- Google developer documentation style guide — Highlights: https://developers.google.com/style/highlights
- Voice and tone: https://developers.google.com/style/tone
- Inclusive documentation: https://developers.google.com/style/inclusive-documentation
- Write for a global audience: https://developers.google.com/style/translation
- Headings and titles: https://developers.google.com/style/headings
- Code samples: https://developers.google.com/style/code-samples
