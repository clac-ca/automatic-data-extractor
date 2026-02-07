export type DocumentDetailTab = "activity" | "preview";
export type DocumentActivityFilter = "all" | "comments" | "events";
export type DocumentPreviewSource = "normalized" | "original";

type DocumentDetailOptions = {
  tab?: DocumentDetailTab;
  activityFilter?: DocumentActivityFilter;
  source?: DocumentPreviewSource;
  sheet?: string | null;
};

type LegacyTab = "data" | "comments" | "timeline";

const VALID_ACTIVITY_FILTERS = new Set<DocumentActivityFilter>([
  "all",
  "comments",
  "events",
]);

function isLegacyTab(value: string | null): value is LegacyTab {
  return value === "data" || value === "comments" || value === "timeline";
}

export function parseDocumentDetailTab(value: string | null): DocumentDetailTab {
  if (value === "preview" || value === "data") return "preview";
  return "activity";
}

export function parseDocumentActivityFilter(
  value: string | null,
  rawTab: string | null = null,
): DocumentActivityFilter {
  if (rawTab === "comments") return "comments";
  if (rawTab === "timeline") return "events";
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
  usesLegacyTab: boolean;
} {
  const rawTab = searchParams.get("tab");
  const rawFilter = searchParams.get("activityFilter");
  const rawSource = searchParams.get("source");
  const rawSheet = searchParams.get("sheet");
  return {
    tab: parseDocumentDetailTab(rawTab),
    activityFilter: parseDocumentActivityFilter(rawFilter, rawTab),
    source: parseDocumentPreviewSource(rawSource),
    sheet: rawSheet && rawSheet.trim().length > 0 ? rawSheet : null,
    usesLegacyTab: isLegacyTab(rawTab),
  };
}

export function normalizeLegacyDocumentDetailSearch(
  searchParams: URLSearchParams,
): URLSearchParams | null {
  const rawTab = searchParams.get("tab");
  if (!isLegacyTab(rawTab)) {
    return null;
  }

  const next = new URLSearchParams(searchParams);
  const state = getDocumentDetailState(searchParams);
  next.set("tab", state.tab);

  if (state.tab === "activity") {
    if (state.activityFilter === "all") {
      next.delete("activityFilter");
    } else {
      next.set("activityFilter", state.activityFilter);
    }
  } else {
    next.delete("activityFilter");
  }

  return next;
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
