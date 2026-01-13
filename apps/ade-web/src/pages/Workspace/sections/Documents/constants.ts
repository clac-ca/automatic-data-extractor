export const DEFAULT_PAGE_SIZE = 50;

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
