export function normalizeConfigStatus(status: unknown): string {
  if (!status) {
    return "";
  }
  if (typeof status === "string") {
    return status.toLowerCase();
  }
  return String(status).toLowerCase();
}

export function sortByUpdatedDesc(a?: string | null, b?: string | null) {
  const dateA = a ? new Date(a).getTime() : 0;
  const dateB = b ? new Date(b).getTime() : 0;
  return dateB - dateA;
}

export function suggestDuplicateName(sourceName: string, existingNames: Set<string>) {
  const base = `Copy of ${sourceName}`.trim();
  if (!existingNames.has(base.toLowerCase())) {
    return base;
  }
  for (let index = 2; index < 100; index += 1) {
    const candidate = `${base} (${index})`;
    if (!existingNames.has(candidate.toLowerCase())) {
      return candidate;
    }
  }
  return `${base} (${Date.now()})`;
}

