export interface DocumentRecord {
  document_id: string;
  workspace_id: string;
  original_filename: string;
  content_type: string | null;
  byte_size: number;
  sha256: string;
  stored_uri: string;
  metadata: Record<string, unknown>;
  expires_at: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  deleted_by: string | null;
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
