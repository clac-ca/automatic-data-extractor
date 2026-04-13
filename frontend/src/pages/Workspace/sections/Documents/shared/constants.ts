import type { ExtendedColumnSort } from "@/types/data-table";

import type { DocumentListRow } from "./types";

export const DOCUMENTS_PAGE_SIZE_OPTIONS = [10, 20, 30, 40, 50, 100, 500, 1000] as const;

export type DocumentsPageSize = (typeof DOCUMENTS_PAGE_SIZE_OPTIONS)[number];

export const DEFAULT_PAGE_SIZE: DocumentsPageSize = 100;

const DOCUMENTS_PAGE_SIZE_OPTION_SET = new Set<number>(DOCUMENTS_PAGE_SIZE_OPTIONS);

export function normalizeDocumentsPageSize(value: number | null | undefined): DocumentsPageSize {
  if (typeof value === "number" && DOCUMENTS_PAGE_SIZE_OPTION_SET.has(value)) {
    return value as DocumentsPageSize;
  }
  return DEFAULT_PAGE_SIZE;
}

export const DEFAULT_SORTING: ExtendedColumnSort<DocumentListRow>[] = [
  { id: "createdAt", desc: true },
];

export const DOCUMENTS_SORT_IDS = new Set([
  "id",
  "name",
  "createdAt",
  "updatedAt",
  "deletedAt",
  "activityAt",
  "lastRunAt",
  "byteSize",
]);

export const DOCUMENTS_FILTER_IDS = new Set([
  "lastRunPhase",
  "name",
  "fileType",
  "tags",
  "assigneeId",
  "mentionedUserId",
  "uploaderId",
  "createdAt",
  "updatedAt",
  "activityAt",
  "byteSize",
]);
