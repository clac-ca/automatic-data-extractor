import type { DocumentStatus, FileType } from "@pages/Workspace/sections/Documents/types";

export type DocumentListRow = {
  id: string;
  workspaceId: string;
  name: string;
  status: DocumentStatus;
  fileType: FileType;
  sizeLabel: string;
  createdAt: string;
};

export type DocumentListResponse = {
  items: DocumentListRow[];
  page: number;
  perPage: number;
  pageCount: number;
  total: number;
  changesCursor: string;
};

export type DocumentsListParams = {
  page: number;
  perPage: number;
  sort: string | null;
  filters: string | null;
  joinOperator: "and" | "or" | null;
  q: string | null;
};
