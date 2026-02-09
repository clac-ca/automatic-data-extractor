import type { components } from "@/types";
import type { FilterItem, FilterJoinOperator } from "@/api/listing";

export type { DocumentPageResult, ListDocumentsQuery } from "@/api/documents";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentListRow = components["schemas"]["DocumentListRow"];
export type DocumentRow = DocumentListRow & {
  uploadProgress?: number | null;
  commentCount?: number | null;
};
export type DocumentRunSummary = components["schemas"]["DocumentRunSummary"];

export type RunResource = components["schemas"]["RunResource"];
export type RunMetricsResource = components["schemas"]["RunMetricsResource"];

export type FileType = "xlsx" | "xls" | "csv" | "pdf" | "unknown";

export type WorkspacePerson = {
  id: string;
  label: string;
  email?: string | null;
};

export type WorkbookSheetPreview = components["schemas"]["WorkbookSheetPreview"];

export type DocumentsListParams = {
  page: number;
  perPage: number;
  sort: string | null;
  q: string | null;
  filters: FilterItem[] | null;
  joinOperator: FilterJoinOperator | null;
};
