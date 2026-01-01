import type { DocumentUploadResponse } from "@api/documents";
import type { components } from "@schema";
import type { UploadManagerItem } from "@hooks/documents/uploadManager";

export type { DocumentPageResult, ListDocumentsQuery } from "@api/documents";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentListRow = components["schemas"]["DocumentListRow"];
export type DocumentChangeEntry = components["schemas"]["DocumentChangeEntry"];
export type DocumentChangesPage = components["schemas"]["DocumentChangesPage"];
export type ApiDocumentStatus = components["schemas"]["DocumentStatus"];
export type ApiDocumentDisplayStatus = components["schemas"]["DocumentDisplayStatus"];
export type DocumentMappingHealth = components["schemas"]["DocumentMappingHealth"];
export type DocumentQueueState = components["schemas"]["DocumentQueueState"];
export type DocumentQueueReason = components["schemas"]["DocumentQueueReason"];
export type DocumentLastRun = components["schemas"]["DocumentLastRun"];

export type WorkspaceMemberOut = components["schemas"]["WorkspaceMemberOut"];
export type WorkspaceMemberPage = components["schemas"]["WorkspaceMemberPage"];

export type RunResource = components["schemas"]["RunResource"];
export type RunPage = components["schemas"]["RunPage"];
export type RunStatus = components["schemas"]["RunStatus"];
export type RunMetricsResource = components["schemas"]["RunMetricsResource"];

export type ConfigurationPage = components["schemas"]["ConfigurationPage"];
export type ConfigurationRecord = components["schemas"]["ConfigurationRecord"];

export type DocumentStatus = components["schemas"]["DocumentDisplayStatus"];
export type ViewMode = "grid" | "board";
export type BoardGroup = "status" | "tag" | "uploader";

export type ListDensity = "comfortable" | "compact";
export type ListRefreshInterval = "auto" | "off" | "30s" | "1m" | "5m";
export type ListPageSize = 50 | 100 | 200 | 1000 | 2000;
export type ListSettings = {
  pageSize: ListPageSize;
  refreshInterval: ListRefreshInterval;
  density: ListDensity;
};

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

export type MappingHealth = DocumentMappingHealth;

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

export type DocumentEntry = Omit<DocumentListRow, "tags"> & {
  tags: string[];
  /** Local-only UI fields. */
  assignee_label: string | null;
  comment_count: number;
  progress?: number;
  error?: DocumentError;
  upload?: UploadManagerItem<DocumentUploadResponse>;
  record?: DocumentListRow;
};

export type BoardColumn = {
  id: string;
  label: string;
  items: DocumentEntry[];
};

export type BoardOption = {
  id: string;
  label: string;
  isDefault?: boolean;
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
