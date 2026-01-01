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

  let updatesAvailable = Boolean(change.requiresRefresh);

  for (let pageIndex = 0; pageIndex < existing.pages.length; pageIndex += 1) {
    const page = existing.pages[pageIndex];
    const items = page.items ?? [];
    if (!items.length) continue;

    const index = items.findIndex((item) => item.id === id);
    if (index === -1) continue;

    if (change.type === "document.deleted") {
      const nextPages = existing.pages.slice();
      nextPages[pageIndex] = {
        ...page,
        items: items.filter((item) => item.id !== id),
      };
      return { data: { ...existing, pages: nextPages }, updatesAvailable, applied: true };
    }

    if (change.type === "document.upsert" && change.row) {
      if (change.matchesFilters === false) {
        const nextPages = existing.pages.slice();
        nextPages[pageIndex] = {
          ...page,
          items: items.filter((item) => item.id !== id),
        };
        return {
          data: { ...existing, pages: nextPages },
          updatesAvailable: true,
          applied: true,
        };
      }

      const nextItems = items.slice();
      nextItems[index] = change.row;
      const nextPages = existing.pages.slice();
      nextPages[pageIndex] = { ...page, items: nextItems };
      return { data: { ...existing, pages: nextPages }, updatesAvailable, applied: true };
    }

    return { data: existing, updatesAvailable, applied: false };
  }

  if (change.type === "document.upsert" && change.row && change.matchesFilters) {
    const firstPage = existing.pages[0];
    if (firstPage) {
      const items = firstPage.items ?? [];
      const insertPosition = resolveInsertPosition(options.sortTokens);
      const nextItems =
        insertPosition === "start" ? [change.row, ...items] : [...items, change.row];
      const nextPages = existing.pages.slice();
      nextPages[0] = { ...firstPage, items: nextItems };
      return { data: { ...existing, pages: nextPages }, updatesAvailable, applied: true };
    }
    updatesAvailable = true;
  }

  return { data: existing, updatesAvailable, applied: false };
}
