import { client } from "@shared/api/client";

import type {
  ConfigRecord,
  ConfigValidationResponse,
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
