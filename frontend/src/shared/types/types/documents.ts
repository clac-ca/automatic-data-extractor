export type DocumentStatus = "uploaded" | "processing" | "processed" | "failed" | "archived";

export type DocumentSource = "manual_upload";

export interface UploaderSummary {
  /** Uploader ULID (26-character string). */
  id: string;
  /** Human-friendly display name if available. */
  name: string | null;
  /** Uploader email address. */
  email: string;
}

export interface DocumentRecord {
  /** Document ULID (26-character string). */
  document_id: string;
  workspace_id: string;
  name: string;
  content_type: string | null;
  byte_size: number;
  metadata: Record<string, unknown>;
  status: DocumentStatus;
  source: DocumentSource;
  expires_at: string;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  deleted_by: string | null;
  tags: string[];
  uploader: UploaderSummary | null;
}

export interface DocumentListResponse {
  items: DocumentRecord[];
  page: number;
  per_page: number;
  has_next: boolean;
  total?: number | null;
}
