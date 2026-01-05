import type { components } from "@schema";

export type { DocumentPageResult, ListDocumentsQuery } from "@api/documents";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentListRow = components["schemas"]["DocumentListRow"];
export type DocumentChangeEntry = components["schemas"]["DocumentChangeEntry"];
export type DocumentResultSummary = components["schemas"]["DocumentResultSummary"];
export type DocumentRunSummary = components["schemas"]["DocumentRunSummary"];

export type RunResource = components["schemas"]["RunResource"];

export type DocumentStatus = components["schemas"]["DocumentStatus"];

export type FileType = "xlsx" | "xls" | "csv" | "pdf" | "unknown";

export type MappingHealth = DocumentResultSummary;

export type WorkspacePerson = {
  /** Stable key for selection and storage. Example: `user:<uuid>` or `label:<email>` */
  key: string;
  label: string;
  kind: "user" | "label";
  userId?: string;
};

export type WorkbookSheetPreview = components["schemas"]["WorkbookSheetPreview"];
