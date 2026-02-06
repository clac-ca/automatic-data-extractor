import type { ExtendedColumnSort, FilterVariant } from "@/types/data-table";

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

export const DOCUMENTS_SIMPLE_FILTERS: Record<string, FilterVariant> = {
  lastRunPhase: "multiSelect",
  fileType: "multiSelect",
  uploaderId: "multiSelect",
  assigneeId: "multiSelect",
  tags: "multiSelect",
  createdAt: "dateRange",
};
