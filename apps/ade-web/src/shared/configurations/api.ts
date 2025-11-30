import { apiFetch, client } from "@shared/api/client";

import { ApiError } from "@shared/api";

import type {
  ConfigurationRecord,
  ConfigurationValidateResponse,
  FileListing,
  FileReadJson,
  FileWriteResponse,
  FileRenameResponse,
  ConfigurationPage,
} from "./types";
import type { paths } from "@schema";

const textEncoder = new TextEncoder();

type ListConfigurationsQuery = paths["/api/v1/workspaces/{workspace_id}/configurations"]["get"]["parameters"]["query"];

export interface ListConfigurationsOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listConfigurations(
  workspaceId: string,
  options: ListConfigurationsOptions = {},
): Promise<ConfigurationPage> {
  const { signal, page, pageSize, includeTotal } = options;
  const query: ListConfigurationsQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configurations", {
    params: {
      path: { workspace_id: workspaceId },
      query,
    },
    signal,
  });

  if (!data) {
    throw new Error("Expected configuration page payload.");
  }

  return data;
}

export async function readConfiguration(
  workspaceId: string,
  configId: string,
  signal?: AbortSignal,
): Promise<ConfigurationRecord | null> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}",
    {
      params: { path: { workspace_id: workspaceId, configuration_id: configId } },
      signal,
    },
  );
  return (data ?? null) as ConfigurationRecord | null;
}

export async function validateConfiguration(
  workspaceId: string,
  configId: string,
): Promise<ConfigurationValidateResponse> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate",
    {
      params: { path: { workspace_id: workspaceId, configuration_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected validation payload.");
  }
  return data as ConfigurationValidateResponse;
}

export async function activateConfiguration(workspaceId: string, configId: string): Promise<ConfigurationRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/activate",
    {
      params: { path: { workspace_id: workspaceId, configuration_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigurationRecord;
}

export async function deactivateConfiguration(workspaceId: string, configId: string): Promise<ConfigurationRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/deactivate",
    {
      params: { path: { workspace_id: workspaceId, configuration_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigurationRecord;
}

export interface ListConfigurationFilesOptions {
  readonly prefix?: string;
  readonly depth?: "0" | "1" | "infinity";
  readonly include?: readonly string[];
  readonly exclude?: readonly string[];
  readonly limit?: number;
  readonly pageToken?: string | null;
  readonly sort?: "path" | "name" | "mtime" | "size";
  readonly order?: "asc" | "desc";
  readonly signal?: AbortSignal;
}

export async function listConfigurationFiles(
  workspaceId: string,
  configId: string,
  options: ListConfigurationFilesOptions = {},
): Promise<FileListing> {
  const { prefix, depth, include, exclude, limit, pageToken, sort, order, signal } = options;
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files",
    {
      params: {
        path: { workspace_id: workspaceId, configuration_id: configId },
        query: {
          prefix: prefix ?? "",
          depth: depth ?? "infinity",
          include: include?.length ? [...include] : undefined,
          exclude: exclude?.length ? [...exclude] : undefined,
          limit,
          page_token: pageToken ?? undefined,
          sort,
          order,
        },
      },
      signal,
      requestInitExt: { cache: "no-store" },
    },
  );
  if (!data) {
    throw new Error("Expected file listing payload.");
  }
  return data as FileListing;
}

export async function readConfigurationFileJson(
  workspaceId: string,
  configId: string,
  filePath: string,
  signal?: AbortSignal,
): Promise<FileReadJson> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}",
    {
      params: {
        path: { workspace_id: workspaceId, configuration_id: configId, file_path: filePath },
      },
      headers: {
        Accept: "application/json",
      },
      signal,
      requestInitExt: { cache: "no-store" },
    },
  );
  if (!data) {
    throw new Error("Expected file payload.");
  }
  return data as FileReadJson;
}

export interface UpsertConfigurationFilePayload {
  readonly path: string;
  readonly content: string;
  readonly parents?: boolean;
  readonly etag?: string | null;
  readonly create?: boolean;
}

export async function upsertConfigurationFile(
  workspaceId: string,
  configId: string,
  payload: UpsertConfigurationFilePayload,
): Promise<FileWriteResponse> {
  const encodedPath = encodeFilePath(payload.path);
  const query = payload.parents ? "?parents=1" : "";
  const response = await apiFetch(
    `/api/v1/workspaces/${workspaceId}/configurations/${configId}/files/${encodedPath}${query}`,
    {
      method: "PUT",
      body: textEncoder.encode(payload.content),
      headers: {
        "Content-Type": "application/octet-stream",
        ...(payload.create ? { "If-None-Match": "*" } : payload.etag ? { "If-Match": payload.etag } : {}),
      },
    },
  );

  if (!response.ok) {
    const problem = await tryParseProblem(response);
    const message = problem?.title ?? `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, problem);
  }

  const data = (await response.json().catch(() => ({}))) as FileWriteResponse;
  if (!data || !data.path) {
    throw new Error("Expected write response payload.");
  }
  return data;
}

export interface RenameConfigurationFilePayload {
  readonly fromPath: string;
  readonly toPath: string;
  readonly overwrite?: boolean;
  readonly destIfMatch?: string | null;
}

export async function renameConfigurationFile(
  workspaceId: string,
  configId: string,
  payload: RenameConfigurationFilePayload,
): Promise<FileRenameResponse> {
  const { data } = await client.PATCH(
    "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}",
    {
      params: {
        path: { workspace_id: workspaceId, configuration_id: configId, file_path: payload.fromPath },
      },
      body: {
        op: "move",
        to: payload.toPath,
        overwrite: payload.overwrite ?? false,
        dest_if_match: payload.destIfMatch ?? undefined,
      },
    },
  );
  if (!data) {
    throw new Error("Expected rename payload.");
  }
  return data as FileRenameResponse;
}

export async function deleteConfigurationFile(
  workspaceId: string,
  configId: string,
  filePath: string,
  options: { etag?: string | null } = {},
): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}", {
    params: {
      path: { workspace_id: workspaceId, configuration_id: configId, file_path: filePath },
    },
    headers: options.etag ? { "If-Match": options.etag } : undefined,
  });
}

export type ConfigurationSourceInput =
  | { readonly type: "template"; readonly templateId: string }
  | { readonly type: "clone"; readonly configurationId: string };

export interface CreateConfigurationPayload {
  readonly displayName: string;
  readonly source: ConfigurationSourceInput;
}

function serializeConfigurationSource(source: ConfigurationSourceInput) {
  if (source.type === "template") {
    return {
      type: "template" as const,
      template_id: source.templateId.trim(),
    };
  }
  return {
    type: "clone" as const,
    configuration_id: source.configurationId.trim(),
  };
}

export async function createConfiguration(
  workspaceId: string,
  payload: CreateConfigurationPayload,
): Promise<ConfigurationRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations",
    {
      params: {
        path: { workspace_id: workspaceId },
      },
      body: {
        display_name: payload.displayName.trim(),
        source: serializeConfigurationSource(payload.source),
      },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigurationRecord;
}

function encodeFilePath(path: string) {
  return path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

async function tryParseProblem(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }
  try {
    return await response.clone().json();
  } catch {
    return undefined;
  }
}
