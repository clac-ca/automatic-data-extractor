import { ApiClient } from "@api/client";

export interface JobRecord {
  readonly jobId: string;
  readonly documentType: string;
  readonly configurationId: string;
  readonly configurationVersion: number;
  readonly status: string;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly createdBy: string;
  readonly inputDocumentId: string;
  readonly metrics: Record<string, unknown>;
  readonly logs: Record<string, unknown>[];
}

interface JobRecordResponse {
  readonly job_id: string;
  readonly document_type: string;
  readonly configuration_id: string;
  readonly configuration_version: number;
  readonly status: string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly created_by: string;
  readonly input_document_id: string;
  readonly metrics: Record<string, unknown>;
  readonly logs: Record<string, unknown>[];
}

export interface ListJobsParams {
  readonly limit?: number;
  readonly offset?: number;
  readonly status?: string;
  readonly inputDocumentId?: string;
}

export async function listJobs(
  client: ApiClient,
  workspaceId: string,
  params: ListJobsParams = {}
): Promise<JobRecord[]> {
  const response = await client.get<JobRecordResponse[]>(
    `/workspaces/${workspaceId}/jobs`,
    {
      query: {
        limit: params.limit,
        offset: params.offset,
        status: params.status,
        input_document_id: params.inputDocumentId
      }
    }
  );

  return response.map(transformJobRecord);
}

function transformJobRecord(record: JobRecordResponse): JobRecord {
  return {
    jobId: record.job_id,
    documentType: record.document_type,
    configurationId: record.configuration_id,
    configurationVersion: record.configuration_version,
    status: record.status,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    createdBy: record.created_by,
    inputDocumentId: record.input_document_id,
    metrics: record.metrics,
    logs: record.logs
  };
}
