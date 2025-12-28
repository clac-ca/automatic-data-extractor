import type { components, paths } from "@schema";
import type { DocumentUploadResponse } from "@shared/documents";
import type { UploadQueueItem } from "@shared/uploads/queue";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentPage = components["schemas"]["DocumentPage"];
export type ApiDocumentStatus = components["schemas"]["DocumentStatus"];
export type DocumentLastRun = components["schemas"]["DocumentLastRun"];
export type ListDocumentsQuery =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];

export type WorkspaceMemberOut = components["schemas"]["WorkspaceMemberOut"];
export type WorkspaceMemberPage = components["schemas"]["WorkspaceMemberPage"];

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

  /**
   * Keys from WorkspacePerson plus special "__unassigned__".
   * If empty => no filtering.
   */
  assignees: string[];
};

export type SavedView = {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  filters: DocumentsFilters;
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

export type WorkspacePerson = {
  /** Stable key for selection and storage. Example: `user:<uuid>` or `label:<email>` */
  key: string;
  label: string;
  kind: "user" | "label";
  userId?: string;
};

export type DocumentComment = {
  id: string;
  documentId: string;
  authorKey: string;
  authorLabel: string;
  body: string;
  createdAt: number;
  updatedAt: number;
  /** Mention labels inserted like `@{Jane Doe}`; keep structured for future notifications */
  mentions: { key: string; label: string }[];
};

export type DocumentEntry = {
  id: string;
  name: string;
  status: DocumentStatus;
  fileType: FileType;
  uploader: string | null;

  /** Collaborative fields (local-first until backend supports them). */
  assigneeKey: string | null;
  assigneeLabel: string | null;
  commentCount: number;

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
