import { get, post, put } from "@shared/api";
import type { components } from "@openapi";

function buildWorkspacePath(workspaceId: string, path: string) {
  return `/workspaces/${workspaceId}${path}`;
}

export async function fetchConfigurations(workspaceId: string, signal?: AbortSignal) {
  return get<ConfigurationRecord[]>(buildWorkspacePath(workspaceId, "/configurations"), { signal });
}

export async function createConfiguration(
  workspaceId: string,
  payload: ConfigurationCreatePayload,
) {
  return post<ConfigurationRecord>(buildWorkspacePath(workspaceId, "/configurations"), payload);
}

export async function activateConfiguration(workspaceId: string, configurationId: string) {
  return post<ConfigurationRecord>(
    buildWorkspacePath(workspaceId, `/configurations/${configurationId}/activate`),
  );
}

export async function fetchConfigurationColumns(
  workspaceId: string,
  configurationId: string,
  signal?: AbortSignal,
) {
  return get<ConfigurationColumn[]>(
    buildWorkspacePath(workspaceId, `/configurations/${configurationId}/columns`),
    { signal },
  );
}

export async function replaceConfigurationColumns(
  workspaceId: string,
  configurationId: string,
  columns: readonly ConfigurationColumnInput[],
) {
  return put<ConfigurationColumn[]>(
    buildWorkspacePath(workspaceId, `/configurations/${configurationId}/columns`),
    columns,
  );
}

export async function createScriptVersion(
  workspaceId: string,
  configurationId: string,
  canonicalKey: string,
  payload: ConfigurationScriptVersionInput,
) {
  return post<ConfigurationScriptVersion>(
    buildWorkspacePath(
      workspaceId,
      `/configurations/${configurationId}/scripts/${encodeURIComponent(canonicalKey)}/versions`,
    ),
    payload,
  );
}

export async function listScriptVersions(
  workspaceId: string,
  configurationId: string,
  canonicalKey: string,
  signal?: AbortSignal,
) {
  return get<ConfigurationScriptVersion[]>(
    buildWorkspacePath(
      workspaceId,
      `/configurations/${configurationId}/scripts/${encodeURIComponent(canonicalKey)}/versions`,
    ),
    { signal },
  );
}

export async function getScriptVersion(
  workspaceId: string,
  configurationId: string,
  canonicalKey: string,
  scriptVersionId: string,
  { includeCode = false, signal }: { includeCode?: boolean; signal?: AbortSignal } = {},
) {
  const query = includeCode ? "?include_code=true" : "";
  return get<ConfigurationScriptVersion>(
    buildWorkspacePath(
      workspaceId,
      `/configurations/${configurationId}/scripts/${encodeURIComponent(
        canonicalKey,
      )}/versions/${scriptVersionId}${query}`,
    ),
    { signal },
  );
}

export async function validateScriptVersion(
  workspaceId: string,
  configurationId: string,
  canonicalKey: string,
  scriptVersionId: string,
  etag?: string,
) {
  const headers: HeadersInit | undefined = etag
    ? {
        "If-Match": toWeakEtag(etag),
      }
    : undefined;
  return post<ConfigurationScriptVersion>(
    buildWorkspacePath(
      workspaceId,
      `/configurations/${configurationId}/scripts/${encodeURIComponent(
        canonicalKey,
      )}/versions/${scriptVersionId}:validate`,
    ),
    undefined,
    { headers },
  );
}

type ConfigurationRecord = components["schemas"]["ConfigurationRecord"];
type ConfigurationCreatePayload = components["schemas"]["ConfigurationCreate"];
type ConfigurationColumn = components["schemas"]["ConfigurationColumnOut"];
type ConfigurationColumnInput = components["schemas"]["ConfigurationColumnIn"];
type ConfigurationScriptVersion = components["schemas"]["ConfigurationScriptVersionOut"];
type ConfigurationScriptVersionInput = components["schemas"]["ConfigurationScriptVersionIn"];

function toWeakEtag(etag: string): string {
  const trimmed = etag.trim();
  if (trimmed.startsWith("W/\"") && trimmed.endsWith("\"")) {
    return trimmed;
  }
  const withoutWeakPrefix = trimmed.startsWith("W/") ? trimmed.slice(2) : trimmed;
  const withoutQuotes = withoutWeakPrefix.replace(/^"|"$/g, "");
  return `W/"${withoutQuotes}"`;
}
