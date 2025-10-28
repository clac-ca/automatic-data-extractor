import { client } from "@shared/api/client";

import type {
  ConfigRecord,
  ConfigScriptContent,
  ConfigScriptSummary,
  ConfigVersionRecord,
  ConfigVersionTestResponse,
  ConfigVersionValidateResponse,
  ManifestEnvelope,
  ManifestEnvelopeWithEtag,
  ManifestPatchRequest,
} from "./types";

export interface ListConfigsOptions {
  readonly includeDeleted?: boolean;
  readonly signal?: AbortSignal;
}

export async function listConfigs(workspaceId: string, options: ListConfigsOptions = {}) {
  const { signal, includeDeleted } = options;
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configs", {
    params: {
      path: { workspace_id: workspaceId },
      query: includeDeleted ? { include_deleted: includeDeleted } : undefined,
    },
    signal,
  });
  return data ?? [];
}

export interface ListConfigVersionsOptions {
  readonly includeDeleted?: boolean;
  readonly signal?: AbortSignal;
}

export async function listConfigVersions(
  workspaceId: string,
  configId: string,
  options: ListConfigVersionsOptions = {},
) {
  const { includeDeleted, signal } = options;
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId },
        query: includeDeleted ? { include_deleted: includeDeleted } : undefined,
      },
      signal,
    },
  );
  return data ?? [];
}

export async function readConfigVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  signal?: AbortSignal,
) {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      signal,
    },
  );
  return data ?? null;
}

export async function createVersion(
  workspaceId: string,
  configId: string,
  payload: { semver: string; message?: string | null; sourceVersionId?: string | null; seedDefaults?: boolean },
) {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/activate",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/restore",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/validate",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/test",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/scripts",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/scripts/{script_path}",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/scripts",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/scripts/{script_path}",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/scripts/{script_path}",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/manifest",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/manifest",
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
    "/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{config_version_id}/clone",
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
