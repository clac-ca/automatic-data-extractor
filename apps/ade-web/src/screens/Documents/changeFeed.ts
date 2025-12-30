import type { InfiniteData } from "@tanstack/react-query";

import type { DocumentChangeEntry, DocumentPageResult, DocumentRecord, DocumentsFilters, DocumentStatus } from "./types";
import { fileTypeFromName, parseTimestamp } from "./utils";
import { UNASSIGNED_KEY } from "./filters";

type MergeOptions = {
  filters: DocumentsFilters;
  search: string;
  sort: string | null;
};

export type MergeChangeResult = {
  data: InfiniteData<DocumentPageResult>;
  updatesAvailable: boolean;
  applied: boolean;
};

export function mergeDocumentChangeIntoPages(
  existing: InfiniteData<DocumentPageResult>,
  change: DocumentChangeEntry,
  options: MergeOptions,
): MergeChangeResult {
  const id = change.document_id ?? change.document?.id;
  if (!id) {
    return { data: existing, updatesAvailable: false, applied: false };
  }

  let found = false;
  let updatesAvailable = false;
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

    if (change.type === "document.upsert" && change.document) {
      const nextDoc = change.document;
      if (!matchesDocumentFilters(nextDoc, options.filters, options.search)) {
        applied = true;
        updatesAvailable = true;
        return {
          ...page,
          items: page.items.filter((item) => item.id !== id),
        };
      }

      const prevDoc = page.items[index];
      if (shouldFlagReorder(prevDoc, nextDoc, options.sort)) {
        updatesAvailable = true;
      }
      const nextItems = page.items.slice();
      nextItems[index] = nextDoc;
      applied = true;
      return { ...page, items: nextItems };
    }

    return page;
  });

  if (!found && change.type === "document.upsert" && change.document) {
    if (matchesDocumentFilters(change.document, options.filters, options.search)) {
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

export function matchesDocumentFilters(
  document: DocumentRecord,
  filters: DocumentsFilters,
  search: string,
): boolean {
  const searchValue = search.trim().toLowerCase();
  const hasSearch = searchValue.length >= 2;

  if (hasSearch) {
    const uploader = document.uploader?.name ?? document.uploader?.email ?? "";
    const haystack = [document.name, uploader, (document.tags ?? []).join(" "), fileTypeFromName(document.name)]
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(searchValue)) return false;
  }

  const statusFilters = filters.statuses;
  if (statusFilters.length > 0) {
    const status = (document.display_status as DocumentStatus | undefined) ?? "queued";
    if (!statusFilters.includes(status)) return false;
  }

  if (filters.fileTypes.length > 0) {
    const fileType = fileTypeFromName(document.name);
    if (!filters.fileTypes.includes(fileType)) return false;
  }

  if (filters.tags.length > 0) {
    const tags = document.tags ?? [];
    if (filters.tagMode === "all") {
      if (!filters.tags.every((t) => tags.includes(t))) return false;
    } else if (!filters.tags.some((t) => tags.includes(t))) {
      return false;
    }
  }

  if (filters.assignees.length > 0) {
    const includeUnassigned = filters.assignees.includes(UNASSIGNED_KEY);
    const assigneeId = document.assignee_user_id;
    if (assigneeId) {
      const assigneeKey = `user:${assigneeId}`;
      if (!filters.assignees.includes(assigneeKey)) return false;
    } else if (!includeUnassigned) {
      return false;
    }
  }

  return true;
}

function shouldFlagReorder(prevDoc: DocumentRecord, nextDoc: DocumentRecord, sort: string | null): boolean {
  if (!sort) return false;
  const field = sort.replace(/^-/, "");
  switch (field) {
    case "activity_at": {
      const prevValue = parseTimestamp(prevDoc.activity_at ?? prevDoc.updated_at);
      const nextValue = parseTimestamp(nextDoc.activity_at ?? nextDoc.updated_at);
      return prevValue !== nextValue;
    }
    case "created_at": {
      const prevValue = parseTimestamp(prevDoc.created_at);
      const nextValue = parseTimestamp(nextDoc.created_at);
      return prevValue !== nextValue;
    }
    case "display_status":
      return prevDoc.display_status !== nextDoc.display_status;
    default:
      return false;
  }
}
