import type { ExtendedColumnSort } from "@/types/data-table";

import type { DocumentListRow } from "./types";

export const DEFAULT_PAGE_SIZE = 20;

export const DEFAULT_SORTING: ExtendedColumnSort<DocumentListRow>[] = [
  { id: "createdAt", desc: true },
];

export const DOCUMENTS_SORT_IDS = new Set([
  "id",
  "name",
  "status",
  "createdAt",
  "updatedAt",
  "activityAt",
  "latestRunAt",
  "byteSize",
]);

export const DOCUMENTS_FILTER_IDS = new Set([
  "status",
  "name",
  "runStatus",
  "fileType",
  "tags",
  "assigneeId",
  "uploaderId",
  "createdAt",
  "updatedAt",
  "activityAt",
  "byteSize",
  "hasOutput",
]);
