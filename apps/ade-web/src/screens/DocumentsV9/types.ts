import type { components, paths } from "@schema";
import type { DocumentUploadResponse } from "@shared/documents";
import type { UploadQueueItem } from "@shared/uploads/queue";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentPage = components["schemas"]["DocumentPage"];
export type ApiDocumentStatus = components["schemas"]["DocumentStatus"];
export type DocumentLastRun = components["schemas"]["DocumentLastRun"];
export type ListDocumentsQuery =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];

export type RunResource = components["schemas"]["RunResource"];
export type RunPage = components["schemas"]["RunPage"];
export type RunStatus = components["schemas"]["RunStatus"];

export type ConfigurationPage = components["schemas"]["ConfigurationPage"];
export type ConfigurationRecord = components["schemas"]["ConfigurationRecord"];

export type DocumentStatus = "queued" | "processing" | "ready" | "failed" | "archived";
export type ViewMode = "grid" | "board";
export type BoardGroup = "status" | "tag" | "uploader";

export type FileType = "xlsx" | "xls" | "csv" | "pdf" | "unknown";
export type TagMode = "any" | "all";

export type DocumentsFilters = {
  statuses: DocumentStatus[];
  fileTypes: FileType[];
  tags: string[];
  tagMode: TagMode;
};

export type DocumentsSavedView = {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  state: {
    search: string;
    sort: string | null;
    viewMode: ViewMode;
    groupBy: BoardGroup;
    filters: DocumentsFilters;
  };
};

export type MappingHealth = {
  attention: number;
  unmapped: number;
  pending?: boolean;
};

export type DocumentError = {
  summary: string;
  detail: string;
  nextStep: string;
};

export type DocumentEntry = {
  id: string;
  name: string;
  status: DocumentStatus;
  uploader: string | null;
  tags: string[];
  createdAt: number;
  updatedAt: number;
  size: string;
  fileType: FileType;
  stage?: string;
  progress?: number;
  error?: DocumentError;
  mapping: MappingHealth;
  record?: DocumentRecord;
  upload?: UploadQueueItem<DocumentUploadResponse>;
};

export type BoardColumn = {
  id: string;
  label: string;
  items: DocumentEntry[];
};

export type WorkbookSheet = {
  name: string;
  headers: string[];
  rows: string[][];
  totalRows: number;
  totalColumns: number;
  truncatedRows: boolean;
  truncatedColumns: boolean;
};

export type WorkbookPreview = {
  sheets: WorkbookSheet[];
};
