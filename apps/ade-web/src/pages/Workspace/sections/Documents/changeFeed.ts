import type { InfiniteData } from "@tanstack/react-query";

import type { DocumentChangeEntry, DocumentPageResult } from "./types";

export type MergeChangeResult = {
  data: InfiniteData<DocumentPageResult>;
  updatesAvailable: boolean;
  applied: boolean;
};

export function mergeDocumentChangeIntoPages(
  existing: InfiniteData<DocumentPageResult>,
  change: DocumentChangeEntry,
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
    if (change.matchesFilters) {
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
