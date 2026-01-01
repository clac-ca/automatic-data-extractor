import type { InfiniteData } from "@tanstack/react-query";

import type { DocumentChangeEntry, DocumentPageResult } from "./types";

export type MergeChangeResult = {
  data: InfiniteData<DocumentPageResult>;
  updatesAvailable: boolean;
  applied: boolean;
};

export type MergeChangeOptions = {
  sortTokens?: string[];
};

const DEFAULT_SORT_TOKENS = ["-createdAt"];

function resolveInsertPosition(sortTokens?: string[]) {
  const tokens = sortTokens && sortTokens.length > 0 ? sortTokens : DEFAULT_SORT_TOKENS;
  const primary = tokens[0] ?? DEFAULT_SORT_TOKENS[0];
  const descending = primary.startsWith("-");
  return descending ? "start" : "end";
}

export function mergeDocumentChangeIntoPages(
  existing: InfiniteData<DocumentPageResult>,
  change: DocumentChangeEntry,
  options: MergeChangeOptions = {},
): MergeChangeResult {
  const id = change.documentId ?? change.row?.id;
  if (!id) {
    return { data: existing, updatesAvailable: false, applied: false };
  }

  let found = false;
  let updatesAvailable = Boolean(change.requiresRefresh);
  let applied = false;

  const nextPages = existing.pages.map((page) => {
    if (!page.items?.length) return page;
    const index = page.items.findIndex((item) => item.id === id);
    if (index === -1) return page;
    found = true;

    if (change.type === "document.deleted") {
      applied = true;
      return {
        ...page,
        items: page.items.filter((item) => item.id !== id),
      };
    }

    if (change.type === "document.upsert" && change.row) {
      const nextDoc = change.row;
      if (change.matchesFilters === false) {
        applied = true;
        updatesAvailable = true;
        return {
          ...page,
          items: page.items.filter((item) => item.id !== id),
        };
      }

      const nextItems = page.items.slice();
      nextItems[index] = nextDoc;
      applied = true;
      return { ...page, items: nextItems };
    }

    return page;
  });

  if (!found && change.type === "document.upsert" && change.row) {
    if (change.matchesFilters && !change.requiresRefresh) {
      const nextPages = existing.pages.slice();
      const firstPage = nextPages[0];
      if (firstPage) {
        const items = firstPage.items ?? [];
        const insertPosition = resolveInsertPosition(options.sortTokens);
        const nextItems =
          insertPosition === "start"
            ? [change.row, ...items]
            : [...items, change.row];
        nextPages[0] = { ...firstPage, items: nextItems };
        return {
          data: { ...existing, pages: nextPages },
          updatesAvailable,
          applied: true,
        };
      }
      updatesAvailable = true;
    } else if (change.matchesFilters) {
      updatesAvailable = true;
    }
  }

  if (!found && !applied) {
    return { data: existing, updatesAvailable, applied: false };
  }

  return {
    data: { ...existing, pages: nextPages },
    updatesAvailable,
    applied,
  };
}
