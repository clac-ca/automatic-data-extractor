export function buildWeakEtag(...parts: Array<string | null | undefined>): string | null {
  const token = parts
    .map((part) => (typeof part === "string" ? part.trim() : ""))
    .filter((part) => part.length > 0)
    .join(":");

  return token.length > 0 ? `W/"${token}"` : null;
}
