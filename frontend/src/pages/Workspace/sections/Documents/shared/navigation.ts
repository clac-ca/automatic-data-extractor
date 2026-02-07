export type DocumentDetailTab = "activity" | "preview";
export type DocumentActivityFilter = "all" | "comments" | "events";
export type DocumentPreviewSource = "normalized" | "original";

type DocumentDetailOptions = {
  tab?: DocumentDetailTab;
  activityFilter?: DocumentActivityFilter;
  source?: DocumentPreviewSource;
  sheet?: string | null;
};

const VALID_ACTIVITY_FILTERS = new Set<DocumentActivityFilter>([
  "all",
  "comments",
  "events",
]);

export function parseDocumentDetailTab(value: string | null): DocumentDetailTab {
  return value === "preview" ? "preview" : "activity";
}

export function parseDocumentActivityFilter(
  value: string | null,
): DocumentActivityFilter {
  if (value && VALID_ACTIVITY_FILTERS.has(value as DocumentActivityFilter)) {
    return value as DocumentActivityFilter;
  }
  return "all";
}

export function parseDocumentPreviewSource(
  value: string | null,
): DocumentPreviewSource {
  return value === "original" ? "original" : "normalized";
}

export function getDocumentDetailState(searchParams: URLSearchParams): {
  tab: DocumentDetailTab;
  activityFilter: DocumentActivityFilter;
  source: DocumentPreviewSource;
  sheet: string | null;
} {
  const rawTab = searchParams.get("tab");
  const rawFilter = searchParams.get("activityFilter");
  const rawSource = searchParams.get("source");
  const rawSheet = searchParams.get("sheet");

  return {
    tab: parseDocumentDetailTab(rawTab),
    activityFilter: parseDocumentActivityFilter(rawFilter),
    source: parseDocumentPreviewSource(rawSource),
    sheet: rawSheet && rawSheet.trim().length > 0 ? rawSheet : null,
  };
}

export function buildDocumentDetailUrl(
  workspaceId: string,
  documentId: string,
  options: DocumentDetailOptions = {},
): string {
  const tab = options.tab ?? "activity";
  const params = new URLSearchParams();

  params.set("tab", tab);

  if (tab === "activity") {
    const filter = options.activityFilter ?? "all";
    if (filter !== "all") {
      params.set("activityFilter", filter);
    }
  } else {
    const source = options.source ?? "normalized";
    params.set("source", source);
    const sheet = options.sheet?.trim();
    if (sheet) {
      params.set("sheet", sheet);
    }
  }

  const query = params.toString();
  return `/workspaces/${workspaceId}/documents/${encodeURIComponent(documentId)}${query ? `?${query}` : ""}`;
}
