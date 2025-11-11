import { apiFetch, client } from "@shared/api/client";

import { ApiError } from "@shared/api";

import type {
  ConfigRecord,
  ConfigScriptContent,
  ConfigVersionRecord,
  ConfigVersionTestResponse,
  ConfigVersionValidateResponse,
  ConfigurationValidateResponse,
  ManifestEnvelope,
  ManifestEnvelopeWithEtag,
  ManifestPatchRequest,
  FileListing,
  FileReadJson,
  FileWriteResponse,
  FileRenameResponse,
} from "./types";

const textEncoder = new TextEncoder();

export interface ListConfigsOptions {
  readonly includeDeleted?: boolean;
  readonly signal?: AbortSignal;
}

export async function listConfigs(
  workspaceId: string,
  options: ListConfigsOptions = {},
): Promise<ConfigRecord[]> {
  const { signal, includeDeleted } = options;
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configurations", {
    params: {
      path: { workspace_id: workspaceId },
      query: includeDeleted ? { include_deleted: includeDeleted } : undefined,
    },
    signal,
  });
  return (data ?? []) as ConfigRecord[];
}

export async function readConfiguration(
  workspaceId: string,
  configId: string,
  signal?: AbortSignal,
): Promise<ConfigRecord | null> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
      signal,
    },
  );
  return (data ?? null) as ConfigRecord | null;
}

export async function validateConfiguration(
  workspaceId: string,
  configId: string,
): Promise<ConfigurationValidateResponse> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/validate",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected validation payload.");
  }
  return data as ConfigurationValidateResponse;
}

export async function activateConfiguration(workspaceId: string, configId: string): Promise<ConfigRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/activate",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigRecord;
}

export async function deactivateConfiguration(workspaceId: string, configId: string): Promise<ConfigRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/deactivate",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigRecord;
}

export interface ListConfigFilesOptions {
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

export async function listConfigFiles(
  workspaceId: string,
  configId: string,
  options: ListConfigFilesOptions = {},
): Promise<FileListing> {
  const { prefix, depth, include, exclude, limit, pageToken, sort, order, signal } = options;
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/files",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId },
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
    },
  );
  if (!data) {
    throw new Error("Expected file listing payload.");
  }
  return data as FileListing;
}

export async function readConfigFileJson(
  workspaceId: string,
  configId: string,
  filePath: string,
  signal?: AbortSignal,
): Promise<FileReadJson> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, file_path: filePath },
      },
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  );
  if (!data) {
    throw new Error("Expected file payload.");
  }
  return data as FileReadJson;
}

export interface UpsertConfigFilePayload {
  readonly path: string;
  readonly content: string;
  readonly parents?: boolean;
  readonly etag?: string | null;
  readonly create?: boolean;
}

export async function upsertConfigFile(
  workspaceId: string,
  configId: string,
  payload: UpsertConfigFilePayload,
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

export interface RenameConfigFilePayload {
  readonly fromPath: string;
  readonly toPath: string;
  readonly overwrite?: boolean;
  readonly destIfMatch?: string | null;
}

export async function renameConfigFile(
  workspaceId: string,
  configId: string,
  payload: RenameConfigFilePayload,
): Promise<FileRenameResponse> {
  const { data } = await client.PATCH(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, file_path: payload.fromPath },
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

export async function deleteConfigFile(
  workspaceId: string,
  configId: string,
  filePath: string,
  options: { etag?: string | null } = {},
): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}", {
    params: {
      path: { workspace_id: workspaceId, config_id: configId, file_path: filePath },
    },
    headers: options.etag ? { "If-Match": options.etag } : undefined,
  });
}

export type ConfigSourceInput =
  | { readonly type: "template"; readonly templateId: string }
  | { readonly type: "clone"; readonly configId: string };

export interface CreateConfigPayload {
  readonly displayName: string;
  readonly source: ConfigSourceInput;
}

function serializeConfigSource(source: ConfigSourceInput) {
  if (source.type === "template") {
    return {
      type: "template" as const,
      template_id: source.templateId.trim(),
    };
  }
  return {
    type: "clone" as const,
    config_id: source.configId.trim(),
  };
}

export async function createConfig(
  workspaceId: string,
  payload: CreateConfigPayload,
): Promise<ConfigRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations",
    {
      params: {
        path: { workspace_id: workspaceId },
      },
      body: {
        display_name: payload.displayName.trim(),
        source: serializeConfigSource(payload.source),
      },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigRecord;
}

export interface ListConfigVersionsOptions {
  readonly includeDeleted?: boolean;
  readonly signal?: AbortSignal;
}

export async function listConfigVersions(
  workspaceId: string,
  configId: string,
  options: ListConfigVersionsOptions = {},
): Promise<ConfigVersionRecord[]> {
  const { includeDeleted, signal } = options;
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId },
        query: includeDeleted ? { include_deleted: includeDeleted } : undefined,
      },
      signal,
    },
  );
  return (data ?? []) as ConfigVersionRecord[];
}

export async function readConfigVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  signal?: AbortSignal,
): Promise<ConfigVersionRecord | null> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      signal,
    },
  );
  return (data ?? null) as ConfigVersionRecord | null;
}

export async function createVersion(
  workspaceId: string,
  configId: string,
  payload: { semver: string; message?: string | null; sourceVersionId?: string | null; seedDefaults?: boolean },
) {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
      body: {
        semver: payload.semver,
        message: payload.message ?? null,
        source_version_id: payload.sourceVersionId ?? null,
        seed_defaults: payload.seedDefaults ?? false,
      },
    },
  );
  if (!data) {
    throw new Error("Expected version payload.");
  }
  return data;
}

export async function activateVersion(workspaceId: string, configId: string, configVersionId: string) {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/activate",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
    },
  );
  if (!data) {
    throw new Error("Expected version payload.");
  }
  return data;
}

export async function archiveVersion(workspaceId: string, configId: string, configVersionId: string) {
  await client.DELETE(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
    },
  );
}

export async function permanentlyDeleteVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
) {
  await client.DELETE(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
        query: { purge: true },
      },
    },
  );
}

export async function restoreVersion(workspaceId: string, configId: string, configVersionId: string) {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/restore",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
    },
  );
  if (!data) {
    throw new Error("Expected version payload.");
  }
  return data;
}

export async function validateVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
): Promise<ConfigVersionValidateResponse> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/validate",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
    },
  );
  if (!data) {
    throw new Error("Expected validation payload.");
  }
  return data;
}

export async function testVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  documentId: string,
  notes?: string | null,
): Promise<ConfigVersionTestResponse> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/test",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      body: {
        document_id: documentId,
        notes: notes ?? null,
      },
    },
  );
  if (!data) {
    throw new Error("Expected test response payload.");
  }
  return data;
}

export async function listScripts(workspaceId: string, configId: string, configVersionId: string, signal?: AbortSignal) {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      signal,
    },
  );
  return data ?? [];
}

export async function readScript(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  scriptPath: string,
  signal?: AbortSignal,
): Promise<ConfigScriptContent | null> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts/{script_path}",
    {
      params: {
        path: {
          workspace_id: workspaceId,
          config_id: configId,
          config_version_id: configVersionId,
          script_path: scriptPath,
        },
      },
      signal,
    },
  );
  return data ?? null;
}

export async function createScript(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  payload: { path: string; template?: string | null; language?: string | null },
): Promise<ConfigScriptContent> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      body: {
        path: payload.path,
        template: payload.template ?? null,
        language: payload.language ?? null,
      },
    },
  );
  if (!data) {
    throw new Error("Expected script payload.");
  }
  return data;
}

export interface UpdateScriptPayload {
  readonly code: string;
  readonly etag?: string | null;
}

export async function updateScript(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  scriptPath: string,
  payload: UpdateScriptPayload,
): Promise<ConfigScriptContent> {
  const { data } = await client.PUT(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts/{script_path}",
    {
      params: {
        path: {
          workspace_id: workspaceId,
          config_id: configId,
          config_version_id: configVersionId,
          script_path: scriptPath,
        },
      },
      body: { code: payload.code },
      headers: payload.etag ? { "If-Match": payload.etag } : undefined,
    },
  );
  if (!data) {
    throw new Error("Expected script payload.");
  }
  return data;
}

export async function deleteScript(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  scriptPath: string,
) {
  await client.DELETE(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts/{script_path}",
    {
      params: {
        path: {
          workspace_id: workspaceId,
          config_id: configId,
          config_version_id: configVersionId,
          script_path: scriptPath,
        },
      },
    },
  );
}

export async function readManifest(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  signal?: AbortSignal,
): Promise<ManifestEnvelopeWithEtag> {
  const { data, response } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/manifest",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      signal,
    },
  );
  if (!data) {
    throw new Error("Expected manifest payload.");
  }
  const etag = response.headers.get("etag");
  return { ...data, etag } as ManifestEnvelopeWithEtag;
}

export async function patchManifest(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  manifest: ManifestPatchRequest,
  etag?: string | null,
): Promise<ManifestEnvelope> {
  const { data } = await client.PATCH(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/manifest",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      body: manifest,
      headers: etag ? { "If-Match": etag } : undefined,
    },
  );
  if (!data) {
    throw new Error("Expected manifest payload.");
  }
  return data;
}

export async function cloneVersion(
  workspaceId: string,
  configId: string,
  sourceVersionId: string,
  options: { semver: string; message?: string | null },
): Promise<ConfigVersionRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/clone",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: sourceVersionId },
      },
      body: {
        semver: options.semver,
        message: options.message ?? null,
      },
    },
  );
  if (!data) {
    throw new Error("Expected version payload.");
  }
  return data;
}

export function findActiveVersion(versions: readonly ConfigVersionRecord[]) {
  return versions.find((version) => version.status === "active" || version.activated_at) ?? null;
}

export function findLatestInactiveVersion(versions: readonly ConfigVersionRecord[]) {
  const inactive = versions.filter((version) => version.status !== "active" && !version.deleted_at);
  return inactive.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] ?? null;
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
