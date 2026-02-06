import { apiFetch, client } from "@/api/client";
import { buildListQuery } from "@/api/listing";
import { ApiError, buildApiErrorMessage, tryParseProblemDetails } from "@/api/errors";

import type {
  ConfigurationPage,
  ConfigurationRecord,
  ConfigurationValidateResponse,
  DirectoryWriteResponse,
  FileListing,
  FileReadJson,
  FileRenameResponse,
  FileWriteResponse,
} from "@/types/configurations";
import type { paths } from "@/types";

type DeleteDirectoryQuery =
  paths["/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}"]["delete"]["parameters"]["query"];
type ImportConfigurationBody =
  paths["/api/v1/workspaces/{workspaceId}/configurations/import"]["post"]["requestBody"]["content"]["multipart/form-data"];
type ReplaceConfigurationBody =
  paths["/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/import"]["put"]["requestBody"]["content"]["multipart/form-data"];
type UpsertConfigurationFileQuery =
  paths["/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}"]["put"]["parameters"]["query"];

export interface ListConfigurationsOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly sort?: string;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listConfigurations(
  workspaceId: string,
  options: ListConfigurationsOptions = {},
): Promise<ConfigurationPage> {
  const { signal, limit, cursor, sort, includeTotal } = options;
  const query = buildListQuery({
    limit,
    cursor: cursor ?? null,
    sort: sort ?? null,
    includeTotal,
  });

  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/configurations", {
    params: {
      path: { workspaceId },
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
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}",
    {
      params: { path: { workspaceId, configurationId: configId } },
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
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/validate",
    {
      params: { path: { workspaceId, configurationId: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected validation payload.");
  }
  return data as ConfigurationValidateResponse;
}

export async function makeActiveConfiguration(workspaceId: string, configId: string): Promise<ConfigurationRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/publish",
    {
      params: { path: { workspaceId, configurationId: configId } },
      body: null,
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigurationRecord;
}

export async function archiveConfiguration(workspaceId: string, configId: string): Promise<ConfigurationRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/archive",
    {
      params: { path: { workspaceId, configurationId: configId } },
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
  readonly cursor?: string | null;
  readonly sort?: "path" | "name" | "mtime" | "size";
  readonly order?: "asc" | "desc";
  readonly signal?: AbortSignal;
}

export async function listConfigurationFiles(
  workspaceId: string,
  configId: string,
  options: ListConfigurationFilesOptions = {},
): Promise<FileListing> {
  const { prefix, depth, include, exclude, limit, cursor, sort, order, signal } = options;
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files",
    {
      params: {
        path: { workspaceId, configurationId: configId },
        query: {
          prefix: prefix ?? "",
          depth: depth ?? "infinity",
          include: include?.length ? [...include] : undefined,
          exclude: exclude?.length ? [...exclude] : undefined,
          limit,
          cursor: cursor ?? undefined,
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
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}",
    {
      params: {
        path: { workspaceId, configurationId: configId, filePath },
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

export interface ExportConfigurationResult {
  readonly blob: Blob;
  readonly filename?: string;
}

export async function exportConfiguration(
  workspaceId: string,
  configId: string,
): Promise<ExportConfigurationResult> {
  const { data, response } = await client.GET(
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/export",
    {
      params: { path: { workspaceId, configurationId: configId } },
      parseAs: "blob",
    },
  );
  if (!data) {
    throw new Error("Expected configuration archive payload.");
  }
  const disposition = response?.headers?.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = filenameMatch?.[1];
  return { blob: data as Blob, filename: filename ?? undefined };
}

export interface UpsertConfigurationFilePayload {
  readonly path: string;
  readonly content: string | Blob | ArrayBuffer;
  readonly parents?: boolean;
  readonly etag?: string | null;
  readonly create?: boolean;
  readonly contentType?: string;
}

export async function upsertConfigurationFile(
  workspaceId: string,
  configId: string,
  payload: UpsertConfigurationFilePayload,
): Promise<FileWriteResponse> {
  const encodedPath = encodeFilePath(payload.path);
  const query: UpsertConfigurationFileQuery = payload.parents ? { parents: true } : {};
  const searchParams = new URLSearchParams();
  if (query.parents) {
    searchParams.set("parents", "true");
  }
  const queryString = searchParams.toString();
  const body = payload.content;
  const contentType =
    payload.contentType ??
    (typeof Blob !== "undefined" && payload.content instanceof Blob && payload.content.type
      ? payload.content.type
      : "application/octet-stream");
  const response = await apiFetch(
    `/api/v1/workspaces/${workspaceId}/configurations/${configId}/files/${encodedPath}${
      queryString ? `?${queryString}` : ""
    }`,
    {
      method: "PUT",
      body,
      headers: {
        "Content-Type": contentType,
        ...(payload.create ? { "If-None-Match": "*" } : payload.etag ? { "If-Match": payload.etag } : {}),
      },
    },
  );

  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = buildApiErrorMessage(problem, response.status);
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
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}",
    {
      params: {
        path: { workspaceId, configurationId: configId, filePath: payload.fromPath },
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
  await client.DELETE("/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}", {
    params: {
      path: { workspaceId, configurationId: configId, filePath },
    },
    headers: options.etag ? { "If-Match": options.etag } : undefined,
  });
}

export async function createConfigurationDirectory(
  workspaceId: string,
  configId: string,
  directoryPath: string,
): Promise<DirectoryWriteResponse> {
  const { data } = await client.PUT(
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}",
    {
      params: {
        path: {
          workspaceId,
          configurationId: configId,
          directoryPath,
        },
      },
    },
  );
  if (!data) {
    throw new Error("Expected directory response payload.");
  }
  return data as DirectoryWriteResponse;
}

export async function deleteConfigurationDirectory(
  workspaceId: string,
  configId: string,
  directoryPath: string,
  options: { recursive?: boolean } = {},
): Promise<void> {
  const query: DeleteDirectoryQuery = {};
  if (options.recursive) {
    query.recursive = true;
  }
  await client.DELETE(
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}",
    {
      params: {
        path: {
          workspaceId,
          configurationId: configId,
          directoryPath,
        },
        query,
      },
    },
  );
}

export interface ImportConfigurationPayload {
  readonly displayName: string;
  readonly file: File | Blob;
}

export async function importConfiguration(
  workspaceId: string,
  payload: ImportConfigurationPayload,
): Promise<ConfigurationRecord> {
  const formData = new FormData();
  formData.append("display_name", payload.displayName);
  formData.append("file", payload.file);

  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/configurations/import", {
    params: { path: { workspaceId } },
    body: formData as unknown as ImportConfigurationBody,
    bodySerializer: () => formData,
  });
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigurationRecord;
}

export interface ReplaceConfigurationPayload {
  readonly file: File | Blob;
  readonly ifMatch?: string | null;
}

export async function replaceConfigurationFromArchive(
  workspaceId: string,
  configId: string,
  payload: ReplaceConfigurationPayload,
): Promise<ConfigurationRecord> {
  const formData = new FormData();
  formData.append("file", payload.file);

  const { data } = await client.PUT(
    "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/import",
    {
      params: { path: { workspaceId, configurationId: configId } },
      headers: payload.ifMatch ? { "If-Match": payload.ifMatch } : undefined,
      body: formData as unknown as ReplaceConfigurationBody,
      bodySerializer: () => formData,
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigurationRecord;
}

export type ConfigurationSourceInput =
  | { readonly type: "template" }
  | { readonly type: "clone"; readonly configurationId: string };

export interface CreateConfigurationPayload {
  readonly displayName: string;
  readonly source: ConfigurationSourceInput;
}

function serializeConfigurationSource(source: ConfigurationSourceInput) {
  if (source.type === "template") {
    return {
      type: "template" as const,
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
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/configurations", {
    params: {
      path: { workspaceId },
    },
    body: {
      display_name: payload.displayName.trim(),
      source: serializeConfigurationSource(payload.source),
    },
  });
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
