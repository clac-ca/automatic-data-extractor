import type { components } from "@schema";
import type { FilterItem, FilterJoinOperator } from "@api/listing";

export type { DocumentPageResult, ListDocumentsQuery } from "@api/documents";

export type DocumentRecord = components["schemas"]["DocumentOut"] & { etag?: string | null };
export type DocumentListRow = components["schemas"]["DocumentListRow"] & { etag?: string | null };
export type DocumentRow = DocumentListRow & { uploadProgress?: number | null };
export type DocumentResultSummary = components["schemas"]["DocumentResultSummary"];
export type DocumentRunSummary = components["schemas"]["DocumentRunSummary"];

export type RunResource = components["schemas"]["RunResource"];

export type DocumentStatus = components["schemas"]["DocumentStatus"];

export type FileType = "xlsx" | "xls" | "csv" | "pdf" | "unknown";

export type MappingHealth = DocumentResultSummary;

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
  filters: FilterItem[] | null;
  joinOperator: FilterJoinOperator | null;
};
