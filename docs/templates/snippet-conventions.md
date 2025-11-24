# Snippet Conventions

Guidelines for presenting code, configuration, and other textual examples in documentation. Consistent formatting helps readers trust and quickly grasp examples.

## General principles

- Introduce every snippet. Precede each code block with a sentence or phrase that tells the reader what the snippet is or does. For example: “The following code sample demonstrates a basic API request:”
- Always specify a language on fenced code blocks for syntax highlighting (for example, `json`, `bash`, `python`).
- Keep examples short—ideally ≤ 30 lines. Split longer examples or link to a full sample file.
- Keep lines near ~80 characters to avoid horizontal scrolling. Break long statements where reasonable.
- Indicate omissions with a language‑appropriate comment (`# ...`, `// ...`). Avoid the Unicode ellipsis character.
- Use clear placeholders for user‑specific values (for example, `<PROJECT_ID>`, `YOUR_API_KEY`, `PATH/TO/FILE`). Explain what to substitute when relevant.
- Never include real secrets, passwords, or private URLs. Use obviously fake/sample values and example domains (for example, `example.com`).
- Prefer copy‑friendly command blocks without shell prompts. If you include prompts for clarity, separate command and output clearly.
- Use consistent indentation (spaces, not tabs) and language‑typical styles (for example, JSON 2 spaces, Python 4 spaces).
- Use backticks for inline code within sentences (for example, filenames, flags, endpoints). Avoid italics/quotes for inline code.

## JSON, YAML, and configuration

- Format JSON and YAML with proper indentation; ensure examples are valid (no trailing commas in JSON).
- Add comments for YAML; JSON does not support comments—explain fields in surrounding prose.
- For large structures, show the relevant top and bottom and elide the middle with comments.

Example (YAML):

```yaml
# config.yaml example
server:
  host: 0.0.0.0   # Server bind address (all interfaces)
  port: 8080      # Server port
database:
  user: admin
  password: "<YOUR_DB_PASSWORD>"  # Replace with a secure password
```

## Command‑line snippets

- Prefer showing only the commands a user should run:

```bash
ade test
```

- If showing output, separate it clearly:

```bash
$ pytest -q
.....................                                                  
21 passed in 3.42s
```

- For local API checks, show concise commands and output:

```bash
curl -s http://localhost:8000/api/health
```

## Good vs. bad examples

When contrasting patterns, label examples clearly and explain why one is preferred.

```js
// Not recommended: Using an implicit global
count = 0;

// Recommended: Encapsulate state
let count = 0;
```

## Snippet checklist

- Introduced with context
- Fenced with a language
- No secrets; placeholders explained
- Clean formatting and indentation
- Omissions clearly indicated
- Copy‑pasteable when possible and correct for its context
