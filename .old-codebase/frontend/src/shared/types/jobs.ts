export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export interface JobRecord {
  readonly job_id: string;
  readonly workspace_id: string;
  readonly configuration_id: string;
  readonly status: JobStatus;
  readonly created_at: string;
  readonly updated_at: string;
  readonly created_by_user_id?: string | null;
  readonly input_document_id: string;
  readonly metrics: Record<string, unknown>;
  readonly logs: ReadonlyArray<Record<string, unknown>>;
}

export interface JobSubmissionPayload {
  readonly input_document_id: string;
  readonly configuration_id: string;
  readonly configuration_version?: number | null;
}
