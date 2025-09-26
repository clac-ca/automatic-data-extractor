import { ApiClient } from "@api/client";

export interface ConfigurationRecord {
  readonly configurationId: string;
  readonly documentType: string;
  readonly title: string;
  readonly version: number;
  readonly isActive: boolean;
  readonly activatedAt: string | null;
  readonly payload: Record<string, unknown>;
  readonly createdAt: string;
  readonly updatedAt: string;
}

interface ConfigurationRecordResponse {
  readonly configuration_id: string;
  readonly document_type: string;
  readonly title: string;
  readonly version: number;
  readonly is_active: boolean;
  readonly activated_at: string | null;
  readonly payload: Record<string, unknown>;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface ListConfigurationsParams {
  readonly documentType?: string;
  readonly isActive?: boolean;
}

export async function listConfigurations(
  client: ApiClient,
  workspaceId: string,
  params: ListConfigurationsParams = {}
): Promise<ConfigurationRecord[]> {
  const response = await client.get<ConfigurationRecordResponse[]>(
    `/workspaces/${workspaceId}/configurations`,
    {
      query: {
        document_type: params.documentType,
        is_active: params.isActive
      }
    }
  );

  return response.map(transformConfigurationRecord);
}

export async function listActiveConfigurations(
  client: ApiClient,
  workspaceId: string,
  documentType?: string
): Promise<ConfigurationRecord[]> {
  const response = await client.get<ConfigurationRecordResponse[]>(
    `/workspaces/${workspaceId}/configurations/active`,
    {
      query: {
        document_type: documentType
      }
    }
  );

  return response.map(transformConfigurationRecord);
}

function transformConfigurationRecord(
  record: ConfigurationRecordResponse
): ConfigurationRecord {
  return {
    configurationId: record.configuration_id,
    documentType: record.document_type,
    title: record.title,
    version: record.version,
    isActive: record.is_active,
    activatedAt: record.activated_at,
    payload: record.payload,
    createdAt: record.created_at,
    updatedAt: record.updated_at
  };
}
