export interface DocstringMetadata {
  readonly name: string | null;
  readonly description: string | null;
  readonly version: string | null;
  readonly summary: string | null;
}

interface ParsedDocstring {
  readonly body: string;
  readonly quote: string;
}

const DOCSTRING_PATTERN = /^(?:\s*(?:#.*\n)*)?\s*((?:[rubf]{0,2})?(["']{3}))([\s\S]*?)(?:\2)/i;

export function parseDocstringMetadata(source: string): DocstringMetadata {
  const match = extractDocstring(source);
  if (!match) {
    return { name: null, description: null, version: null, summary: null };
  }

  const lines = match.body
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const metadata: DocstringMetadata = {
    name: null,
    description: null,
    version: null,
    summary: null,
  };

  const remaining: string[] = [];

  for (const line of lines) {
    const kvMatch = /^([A-Za-z][A-Za-z0-9 _-]*):\s*(.*)$/.exec(line);
    if (kvMatch) {
      const key = kvMatch[1].toLowerCase();
      const value = kvMatch[2].trim();
      if (key === "name" && value) {
        metadata.name = value;
      } else if (key === "description" && value) {
        metadata.description = value;
      } else if ((key === "version" || key === "semver") && value) {
        metadata.version = value;
      } else if (key === "summary" && value) {
        metadata.summary = value;
      } else {
        remaining.push(line);
      }
    } else {
      remaining.push(line);
    }
  }

  if (!metadata.summary && remaining.length > 0) {
    metadata.summary = remaining[0];
  }

  if (!metadata.description && remaining.length > 0) {
    metadata.description = remaining.join(" ");
  }

  return metadata;
}

function extractDocstring(source: string): ParsedDocstring | null {
  const match = DOCSTRING_PATTERN.exec(source);
  if (!match) {
    return null;
  }
  return { body: match[3] ?? "", quote: match[2] ?? "" };
}
