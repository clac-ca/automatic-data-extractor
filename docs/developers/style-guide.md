# Developer Documentation Style Guide

This guide defines the voice, tone, and formatting conventions for all our developer documentation. Adhering to a consistent style ensures that readers have a clear, friendly, and helpful experience across all docs. The guidelines below align with widely accepted technical writing practices (for example, Google’s developer documentation style), adapted to our project's needs.

---

## Voice and Tone

Write in a conversational, friendly tone without being frivolous. Aim to sound like a knowledgeable friend advising the reader, not a formal thesis or a sales pitch. Use second person ("you") to address the reader directly, and imperative mood for instructions. For example, instead of saying "we will now do X," instruct "do X." Writing in second person and active voice makes it clear who should do what. Always prefer active constructions ("The system sends an email" rather than "An email is sent by the system").

Maintain a respectful and inclusive voice. Avoid slang, colloquialisms, or jargon that might not be universally understood. Jargon or buzzwords should be used only when they are standard terms in the technical domain—otherwise, explain them or choose simpler words. Steer clear of humor, pop-culture references, or idioms that could confuse or exclude international readers. For example, don’t assume the reader knows a phrase like "hit it out of the park"—replace idioms with clear, literal descriptions. Likewise, avoid ableist or sexist terms; use neutral alternatives (for instance, "give a final check" instead of "give a final sanity check"). Write with a global audience in mind by using clear, straightforward language and explaining context when needed.

Tone should be encouraging and matter-of-fact. It’s good to be positive and empowering, but do not overuse words like "simple" or "easy," as what’s "simple" for one user may not be for another. Similarly, avoid phrases that could be seen as condescending (for example, "just do X," "obviously," "simply"). Be polite but don’t overuse "please" in instructional steps (for example, "Click **Submit**," not "Please click **Submit**"). It’s fine to say "please" in explanatory text when appropriate to maintain a courteous tone, but in step-by-step instructions it usually adds unnecessary formality.

Avoid common pitfalls: overly cutesy language, unnecessary exclamation marks, repetitive sentence starts (for example, every sentence beginning with "You can …"), and filler phrases like "Note that …" or "At this time." Also avoid writing as "let’s …" or "we will …" when giving instructions—it’s clearer and more direct to address the reader as "you" or to use imperatives. Do not refer to the documentation or product as "we"; the focus is on the user’s actions and the software’s behavior.

> Not recommended: “Let’s now configure the environment for our app.”
>
> Recommended: “Configure the environment for your app.”

> Not recommended: “Just hit the **Submit** button and you’re good to go!”
>
> Recommended: “Click **Submit** to send the form.”

---

## Language and Grammar

- Use standard American English spelling and grammar throughout.
- Write in present tense for general statements and procedural steps. For example, write "This API returns the data …" rather than "This API will return the data …" Use future tense only when describing something that truly happens later or is conditional. Past tense is rarely needed except in historical references or release notes.
- Keep sentences concise and clear. Break down long, complex sentences into shorter ones to improve readability (and translatability). Each sentence should convey one idea. Avoid run-on sentences or excessive subclauses that could confuse readers. Avoid double negatives or overly complex phrasing; say "X is allowed" rather than "it is not disallowed to do X."
- Use active voice consistently. Passive voice can obscure who is responsible for an action. For example, "The configuration is initialized by the script" is weaker than "The script initializes the configuration." There may be rare cases to use passive (if the actor is unknown or unimportant), but generally prefer active constructions for clarity.
- Put conditions before instructions. If a step is conditional, lead with the condition: "If you have not installed the CLI, install it now." rather than "Install the CLI if you have not already done so."
- Use second person pronouns ("you") to refer to the reader, and prefer neutral/gender-inclusive language. For example, instead of "the admin should update his configuration," say "you should update the configuration" or "the administrator should update the configuration."
- When using abbreviations or acronyms, spell them out on first use with the abbreviation in parentheses, unless they are very common (like HTTP or JSON). For example: "Use the Cloud Execution Manager (CEM) to orchestrate tasks …" On subsequent references, just CEM is fine.
- If a term is defined in our glossary, link the first occurrence of that term on a page to the glossary entry (for example, `docs/developers/02-glossary.md#widget-engine`). Be consistent in terminology: use the same term or phrase for the same concept throughout the documentation.

---

## Structure and Formatting

### Titles and headings

- Start each page with a single level‑1 heading (H1) as the page title.
- Use Title Case for the page title (capitalize major words) and sentence case for section headings (H2 and below).
- Ensure each page has exactly one H1; organize subheadings hierarchically without skipping levels.
- Prefer imperative headings for task‑oriented sections (for example, "Create an instance" → "Create an instance"). Use noun phrases for conceptual sections (for example, "Architecture overview"). Avoid gerunds (“-ing”) in headings when possible.
- Begin each major section with a brief introductory paragraph. Aim for 3–5 sentence paragraphs.

### Lists

- Use bulleted lists for unordered items; use numbered lists for sequences or procedures.
- Keep items parallel in structure (all start with a verb, or all are noun phrases).
- Capitalize list items consistently. If any item is a full sentence, punctuate all items; otherwise, omit terminal punctuation.
- Use the Oxford comma in any series of three or more items (for example, "Windows, Linux, and macOS").

### Emphasis and formatting

- Use bold for UI elements (buttons, menu items, field names), for example, "Click **Deploy**."
- Use `code font` (backticks) for filenames, code identifiers, commands, endpoints, config keys, and literal values.
- Reserve italics for introducing terms or rare emphasis.
- Use unambiguous dates (for example, "February 10, 2025"). Include time zones for times (for example, "5:00 PM UTC"). Avoid time‑relative phrases ("today," "currently"); prefer versioned or timeless phrasing.

---

## Links and Cross‑References

- Use descriptive link text (avoid "click here" or bare URLs).
- Use relative links for internal pages (for example, `[Overview](./README.md)`).
- Link the first mention of defined terms to their glossary or reference entry; one link per page is usually sufficient.
- For external resources, link the official title (for example, "See the **TensorFlow documentation**"). Periodically verify links.

---

## Code Samples and Snippets

See `docs/developers/00-templates/snippet-conventions.md` for full details. Core principles:

- Introduce code examples with a brief sentence stating what they show. End with a colon when leading directly into a block.
- Use fenced code blocks with language hints (`bash`, `python`, `json`, and so on). Keep lines near 80 characters when practical.
- Show realistic but minimal code (typically ≤ 30 lines). Omit boilerplate and indicate omissions with a language‑appropriate comment (`# ...`, `// ...`). Avoid the Unicode ellipsis character.
- Use clear placeholders for user‑specific values (for example, `<PROJECT_ID>`, `YOUR_API_KEY`). Never include secrets or private data.
- If a snippet is particularly important, label it in prose (for example, "Minimal example:").

Example (YAML with an elided section):

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

## Figures and Media

Use diagrams and images only when they aid understanding. Prefer text‑based diagrams (ASCII art) or tables for maintainability and accessibility. Keep ASCII diagrams ≤ 80 characters wide and explain them in surrounding text.

When images are necessary (for example, screenshots or complex architecture diagrams), provide concise alt text. Use high‑quality assets and optimize for size. Prefer SVG for diagrams and PNG/JPEG for screenshots. Introduce images in the text; include captions if additional context helps.

Always protect privacy and security: scrub identifying data and use representative placeholders (for example, "ACME Corp," "Alice," "Bob").

---

## Document Structure and Navigation

Clearly state the audience and goal at the top of a page, so readers know who the page is for and what outcome to expect. In longer guides or tutorials, include "Next steps" at the end with logical follow‑ups or related links. Conclude with a quick summary of what was accomplished.

---

## Additional Guidelines

- Consistency: Keep terminology and structure consistent across pages.
- Accessibility and inclusion: Use inclusive language and accessible patterns (heading order, alt text, no information conveyed by color alone).
- Evergreen phrasing: Prefer versioned or timeless phrasing (for example, "In version 4.2, Feature X is deprecated"). Avoid short‑lived words like "currently."
- Review: Proofread or request a peer review for clarity and adherence to this guide.

---

## References

- Google developer documentation style guide — Highlights: https://developers.google.com/style/highlights
- Voice and tone: https://developers.google.com/style/tone
- Inclusive documentation: https://developers.google.com/style/inclusive-documentation
- Write for a global audience: https://developers.google.com/style/translation
- Headings and titles: https://developers.google.com/style/headings
- Code samples: https://developers.google.com/style/code-samples
