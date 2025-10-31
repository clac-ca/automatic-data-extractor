import { client } from "@shared/api/client";

import type {
  ConfigRecord,
  ConfigSecretInput,
  ConfigSecretMetadata,
  ConfigValidationResponse,
  FileItem,
  Manifest,
  ManifestInput,
} from "./types";

export interface ListConfigsOptions {
  readonly statuses?: readonly string[] | null;
  readonly signal?: AbortSignal;
}

export async function listConfigs(workspaceId: string, options: ListConfigsOptions = {}) {
  const { signal, statuses } = options;
  const query = statuses && statuses.length > 0 ? { status: Array.from(statuses) } : undefined;
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configs", {
    params: {
      path: { workspace_id: workspaceId },
      query,
    },
    signal,
  });
  return data ?? [];
}

export async function getConfig(workspaceId: string, configId: string, signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configs/{config_id}", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
    signal,
  });
  if (!data) return null;
  return data as ConfigRecord;
}

export interface CreateConfigPayload {
  readonly title?: string | null;
  readonly note?: string | null;
  readonly fromConfigId?: string | null;
}

export async function createConfig(workspaceId: string, payload: CreateConfigPayload) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/configs", {
    params: { path: { workspace_id: workspaceId } },
    body: {
      title: payload.title ?? undefined,
      note: payload.note ?? undefined,
      from_config_id: payload.fromConfigId ?? undefined,
    },
  });
  if (!data) throw new Error("Expected config payload.");
  return data as ConfigRecord;
}

export interface CloneConfigPayload {
  readonly title: string;
  readonly note?: string | null;
}

export async function cloneConfig(
  workspaceId: string,
  configId: string,
  payload: CloneConfigPayload,
) {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/clone",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
      body: {
        title: payload.title,
        note: payload.note ?? undefined,
      },
    },
  );
  if (!data) throw new Error("Expected config payload.");
  return data as ConfigRecord;
}

export interface ImportConfigPayload {
  readonly archive: File;
  readonly title?: string | null;
  readonly note?: string | null;
}

export async function importConfig(workspaceId: string, payload: ImportConfigPayload) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/configs/import", {
    params: { path: { workspace_id: workspaceId } },
    body: {
      title: payload.title ?? undefined,
      note: payload.note ?? undefined,
      archive: payload.archive,
    } as Record<string, unknown>,
    bodySerializer: () => {
      const formData = new FormData();
      if (payload.title && payload.title.trim().length > 0) {
        formData.append("title", payload.title.trim());
      }
      if (payload.note && payload.note.trim().length > 0) {
        formData.append("note", payload.note.trim());
      }
      formData.append("archive", payload.archive);
      return formData;
    },
  });
  if (!data) throw new Error("Expected config payload.");
  return data as ConfigRecord;
}

export interface ExportConfigResult {
  readonly blob: Blob;
  readonly filename: string;
}

export async function exportConfig(workspaceId: string, configId: string): Promise<ExportConfigResult> {
  const { data, response } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/export",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
      parseAs: "blob",
    },
  );
  if (!data) throw new Error("Expected export payload.");
  const header = response.headers.get("content-disposition") ?? "";
  const filename = extractFilename(header) ?? `${configId}.zip`;
  return { blob: data, filename };
}

export interface UpdateConfigPayload {
  readonly title?: string | null;
  readonly note?: string | null;
  readonly version?: string | null;
  readonly status?: "inactive" | "archived";
}

export async function updateConfig(
  workspaceId: string,
  configId: string,
  payload: UpdateConfigPayload,
) {
  const body: Record<string, unknown> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.note !== undefined) body.note = payload.note;
  if (payload.version !== undefined) body.version = payload.version;
  if (payload.status !== undefined) body.status = payload.status;
  const { data } = await client.PATCH("/api/v1/workspaces/{workspace_id}/configs/{config_id}", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
    body,
  });
  if (!data) throw new Error("Expected config payload.");
  return data as ConfigRecord;
}

export async function deleteConfig(workspaceId: string, configId: string) {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/configs/{config_id}", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
  });
}

export async function activateConfig(workspaceId: string, configId: string) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/configs/{config_id}/activate", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
  });
  if (!data) throw new Error("Expected config payload.");
  return data as ConfigRecord;
}

export async function readManifest(workspaceId: string, configId: string, signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configs/{config_id}/manifest", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
    signal,
  });
  if (!data) return null;
  return data as Manifest;
}

export async function writeManifest(
  workspaceId: string,
  configId: string,
  manifest: ManifestInput,
) {
  const { data } = await client.PUT("/api/v1/workspaces/{workspace_id}/configs/{config_id}/manifest", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
    body: manifest,
  });
  if (!data) throw new Error("Expected manifest payload.");
  return data as Manifest;
}

export async function validateConfig(workspaceId: string, configId: string) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/configs/{config_id}/validate", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
  });
  if (!data) throw new Error("Expected validation payload.");
  return data as ConfigValidationResponse;
}

export async function listSecrets(workspaceId: string, configId: string, signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configs/{config_id}/secrets", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
    signal,
  });
  return (data ?? []) as ConfigSecretMetadata[];
}

export async function upsertSecret(
  workspaceId: string,
  configId: string,
  payload: ConfigSecretInput,
) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/configs/{config_id}/secrets", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
    body: payload,
  });
  if (!data) throw new Error("Expected secret metadata payload.");
  return data as ConfigSecretMetadata;
}

export async function deleteSecret(workspaceId: string, configId: string, name: string) {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/configs/{config_id}/secrets/{name}", {
    params: { path: { workspace_id: workspaceId, config_id: configId, name } },
  });
}

export async function listConfigFiles(workspaceId: string, configId: string, signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configs/{config_id}/files", {
    params: { path: { workspace_id: workspaceId, config_id: configId } },
    signal,
  });
  return (data ?? []) as FileItem[];
}

export async function readConfigFile(
  workspaceId: string,
  configId: string,
  path: string,
  signal?: AbortSignal,
) {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/files/{path}",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId, path } },
      signal,
    },
  );
  if (typeof data !== "string") {
    throw new Error("Expected file content to be returned as text.");
  }
  return data;
}

export async function writeConfigFile(
  workspaceId: string,
  configId: string,
  path: string,
  content: string,
) {
  const { data } = await client.PUT(
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/files/{path}",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId, path } },
      body: content,
      headers: { "Content-Type": "text/plain" },
    },
  );
  if (!data) throw new Error("Expected file metadata payload.");
  return data as FileItem;
}

export async function deleteConfigFile(workspaceId: string, configId: string, path: string) {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/configs/{config_id}/files/{path}", {
    params: { path: { workspace_id: workspaceId, config_id: configId, path } },
  });
}

function extractFilename(contentDisposition: string) {
  if (!contentDisposition) {
    return null;
  }
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const simpleMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return simpleMatch?.[1] ?? null;
}
