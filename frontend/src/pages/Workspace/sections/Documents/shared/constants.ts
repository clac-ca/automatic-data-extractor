import type { ExtendedColumnSort } from "@/types/data-table";

import type { DocumentListRow } from "./types";

export const DEFAULT_PAGE_SIZE = 20;

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
  "uploaderId",
  "createdAt",
  "updatedAt",
  "activityAt",
  "byteSize",
]);
