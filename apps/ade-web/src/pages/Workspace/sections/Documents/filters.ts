import type { FilterItem } from "@api/listing";
import type { DocumentStatus, DocumentsFilters, SavedView } from "./types";

export const UNASSIGNED_KEY = "__unassigned__";

export const ACTIVE_DOCUMENT_STATUSES: DocumentStatus[] = ["uploaded", "processing", "processed", "failed"];

export const DEFAULT_DOCUMENT_FILTERS: DocumentsFilters = {
  statuses: [],
  fileTypes: [],
  tags: [],
  tagMode: "any",
  assignees: [],
};

export function buildDocumentFilterItems(filters: DocumentsFilters): FilterItem[] {
  const items: FilterItem[] = [];

  if (filters.statuses.length > 0) {
    items.push({ id: "status", operator: "in", value: filters.statuses });
  }

  if (filters.fileTypes.length > 0) {
    const fileTypes = filters.fileTypes.filter((type) => type !== "unknown");
    if (fileTypes.length > 0) {
      items.push({ id: "fileType", operator: "in", value: fileTypes });
    }
  }

  if (filters.tags.length > 0) {
    if (filters.tagMode === "all") {
      filters.tags.forEach((tag) => {
        items.push({ id: "tags", operator: "eq", value: tag });
      });
    } else {
      items.push({ id: "tags", operator: "in", value: filters.tags });
    }
  }

  if (filters.assignees.length > 0) {
    const { assigneeIds, includeUnassigned } = normalizeAssignees(filters.assignees);
    if (assigneeIds.length > 0 || includeUnassigned) {
      const values = includeUnassigned ? [...assigneeIds, null] : assigneeIds;
      items.push({ id: "assigneeId", operator: "in", value: values });
    }
  }

  return items;
}

export type BuiltInViewId =
  | "all_documents"
  | "active_documents"
  | "assigned_to_me"
  | "assigned_to_me_or_unassigned"
  | "unassigned"
  | "processed"
  | "processing"
  | "failed"
  | "archived";

export type BuiltInViewCounts = {
  total: number;
  active: number;
  assignedToMe: number;
  assignedToMeOrUnassigned: number;
  unassigned: number;
  processed: number;
  processing: number;
  failed: number;
  archived: number;
};

export function buildBuiltInViews(counts: BuiltInViewCounts) {
  return [
    { id: "all_documents", label: "All documents", count: counts.total },
    { id: "active_documents", label: "Active documents", count: counts.active },
    { id: "assigned_to_me", label: "Assigned to me", count: counts.assignedToMe },
    {
      id: "assigned_to_me_or_unassigned",
      label: "Assigned to me or Unassigned",
      count: counts.assignedToMeOrUnassigned,
    },
    { id: "unassigned", label: "Unassigned", count: counts.unassigned },
    { id: "processed", label: "Processed", count: counts.processed },
    { id: "processing", label: "Processing", count: counts.processing },
    { id: "failed", label: "Failed", count: counts.failed },
    { id: "archived", label: "Archived", count: counts.archived },
  ] as const;
}

export function buildFiltersForBuiltInView(id: BuiltInViewId, currentUserKey: string): DocumentsFilters {
  const cleared = { ...DEFAULT_DOCUMENT_FILTERS };

  switch (id) {
    case "active_documents":
      return { ...cleared, statuses: [...ACTIVE_DOCUMENT_STATUSES] };
    case "assigned_to_me":
      return { ...cleared, assignees: [currentUserKey] };
    case "assigned_to_me_or_unassigned":
      return { ...cleared, assignees: [currentUserKey, UNASSIGNED_KEY] };
    case "unassigned":
      return { ...cleared, assignees: [UNASSIGNED_KEY] };
    case "processed":
      return { ...cleared, statuses: ["processed"] };
    case "processing":
      return { ...cleared, statuses: ["uploaded", "processing"] };
    case "failed":
      return { ...cleared, statuses: ["failed"] };
    case "archived":
      return { ...cleared, statuses: ["archived"] };
    case "all_documents":
    default:
      return cleared;
  }
}

function sameSet<T>(left: T[], right: T[]) {
  if (left.length !== right.length) {
    const leftSet = new Set(left);
    const rightSet = new Set(right);
    if (leftSet.size !== rightSet.size) return false;
    for (const value of leftSet) {
      if (!rightSet.has(value)) return false;
    }
    return true;
  }
  const rightSet = new Set(right);
  for (const value of left) {
    if (!rightSet.has(value)) return false;
  }
  return true;
}

export function filtersEqual(a: DocumentsFilters, b: DocumentsFilters) {
  const tagModeMatches = a.tags.length === 0 && b.tags.length === 0 ? true : a.tagMode === b.tagMode;
  return (
    tagModeMatches &&
    sameSet(a.statuses, b.statuses) &&
    sameSet(a.fileTypes, b.fileTypes) &&
    sameSet(a.tags, b.tags) &&
    sameSet(a.assignees, b.assignees)
  );
}

export function resolveBuiltInViewId(filters: DocumentsFilters, currentUserKey: string): BuiltInViewId | null {
  const builtIns: BuiltInViewId[] = [
    "all_documents",
    "active_documents",
    "assigned_to_me",
    "assigned_to_me_or_unassigned",
    "unassigned",
    "processed",
    "processing",
    "failed",
    "archived",
  ];

  for (const id of builtIns) {
    const target = buildFiltersForBuiltInView(id, currentUserKey);
    if (filtersEqual(filters, target)) return id;
  }
  return null;
}

export function resolveActiveViewId(
  filters: DocumentsFilters,
  search: string,
  savedViews: SavedView[],
  currentUserKey: string,
) {
  if (search.trim().length >= 2) return "custom";
  const builtIn = resolveBuiltInViewId(filters, currentUserKey);
  if (builtIn) return builtIn;
  const saved = savedViews.find((view) => filtersEqual(view.filters, filters));
  return saved?.id ?? "custom";
}

export function normalizeAssignees(assignees: string[]) {
  const assigneeIds = assignees
    .filter((key) => key.startsWith("user:"))
    .map((key) => key.slice(5))
    .filter(Boolean);
  const includeUnassigned = assignees.includes(UNASSIGNED_KEY);
  return { assigneeIds, includeUnassigned };
}

export function assigneeKeysFromIds(assigneeIds: string[], includeUnassigned: boolean) {
  const keys = assigneeIds.map((id) => `user:${id}`).filter(Boolean);
  if (includeUnassigned) keys.push(UNASSIGNED_KEY);
  return keys;
}
