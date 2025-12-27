import type { components, paths } from "@schema";
import type { DocumentUploadResponse } from "@shared/documents";
import type { UploadQueueItem } from "@shared/uploads/queue";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentPage = components["schemas"]["DocumentPage"];
export type ApiDocumentStatus = components["schemas"]["DocumentStatus"];
export type DocumentLastRun = components["schemas"]["DocumentLastRun"];
export type ListDocumentsQuery =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];

export type DocumentStatus = "queued" | "processing" | "ready" | "failed" | "archived";
export type ViewMode = "grid" | "board";
export type BoardGroup = "status" | "tag" | "uploader";

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
