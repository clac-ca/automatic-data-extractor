import { API_BASE_URL } from "./client";
import { ApiError } from "./errors";

export interface ConfigurationRecord {
  configuration_id: string;
  document_type: string;
  title: string;
  version: number;
  is_active: boolean;
  activated_at: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface FetchOptions {
  documentType?: string | null;
}

async function parseJson(response: Response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new ApiError("Invalid response from server", response.status, text);
  }
}

export async function fetchActiveConfigurations(
  token: string,
  workspaceId: string,
  options: FetchOptions = {},
): Promise<ConfigurationRecord[]> {
  const url = new URL(
    `${API_BASE_URL}/workspaces/${workspaceId}/configurations/active`,
    window.location.origin,
  );

  if (options.documentType) {
    url.searchParams.set("document_type", options.documentType);
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const payload = await parseJson(response).catch(() => null);
    const message =
      (payload && typeof payload.detail === "string"
        ? payload.detail
        : response.statusText) || "Failed to load configurations";
    throw new ApiError(message, response.status, payload);
  }

  const payload = await parseJson(response);
  if (!Array.isArray(payload)) {
    throw new ApiError(
      "Unexpected configurations response",
      response.status,
      payload,
    );
  }

  return payload as ConfigurationRecord[];
}

export function uniqueDocumentTypes(
  configurations: ConfigurationRecord[] | undefined,
): string[] {
  if (!configurations) {
    return [];
  }
  const seen = new Set<string>();
  const types: string[] = [];
  for (const configuration of configurations) {
    const { document_type: documentType } = configuration;
    if (!seen.has(documentType)) {
      seen.add(documentType);
      types.push(documentType);
    }
  }
  return types;
}

export function describeConfiguration(configuration: ConfigurationRecord): string {
  const version = `v${configuration.version}`;
  return `${configuration.title} (${version})`;
}
