export interface UploaderSummary {
  id: string;
  name: string | null;
  email: string;
}

export interface DocumentRecord {
  document_id: string;
  workspace_id: string;
  name: string;
  content_type: string | null;
  byte_size: number;
  metadata: Record<string, unknown>;
  status: string;
  source: string;
  expires_at: string;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  deleted_by: string | null;
  tags: string[];
  uploader: UploaderSummary | null;
}

export interface WorkspaceDocumentSummary {
  id: string;
  name: string;
  updatedAt: string;
  createdAt: string;
  byteSize: number;
  contentType: string | null;
  metadata: Record<string, unknown>;
}
