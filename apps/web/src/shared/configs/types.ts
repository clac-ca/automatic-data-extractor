import type { components } from "@openapi";

export type ConfigRecord = components["schemas"]["ConfigRecord"];
export type ConfigVersionRecord = components["schemas"]["ConfigVersionRecord"];
export type ConfigScriptSummary = components["schemas"]["ConfigScriptSummary"];
export type ConfigScriptContent = components["schemas"]["ConfigScriptContent"];
export type ConfigVersionValidateResponse = components["schemas"]["ConfigVersionValidateResponse"];
export type ConfigVersionTestResponse = components["schemas"]["ConfigVersionTestResponse"];
export type ConfigurationValidateResponse = components["schemas"]["ConfigurationValidateResponse"];
export type ManifestResponse = components["schemas"]["ManifestResponse"];
export type ManifestPatchRequest = components["schemas"]["ManifestPatchRequest"];

export type ManifestEnvelope = ManifestResponse;
export interface ManifestEnvelopeWithEtag extends ManifestEnvelope {
  readonly etag?: string | null;
}

export type ConfigManifest = ManifestEnvelope["manifest"];

export interface ManifestColumn {
  readonly key: string;
  readonly label: string;
  readonly path: string;
  readonly ordinal: number;
  readonly required?: boolean;
  readonly enabled?: boolean;
  readonly depends_on?: readonly string[];
}

export interface ManifestTableSection {
  readonly transform?: { readonly path: string } | null;
  readonly validators?: { readonly path: string } | null;
}

export interface ParsedManifest {
  readonly name: string;
  readonly filesHash: string;
  readonly columns: ManifestColumn[];
  readonly table?: ManifestTableSection;
  readonly raw: ConfigManifest;
}

export interface ConfigFileEntry {
  readonly path: string;
  readonly type: "file" | "dir";
  readonly size?: number;
  readonly mtime?: string;
  readonly etag?: string;
}

export interface ConfigFileListing {
  readonly root: string;
  readonly entries: readonly ConfigFileEntry[];
}

export interface ConfigFileContent {
  readonly path: string;
  readonly encoding: "utf-8" | "base64";
  readonly content: string;
  readonly etag?: string | null;
  readonly size?: number;
  readonly mtime?: string;
}

export interface ConfigFileWriteResponse {
  readonly path: string;
  readonly size?: number;
  readonly mtime?: string;
  readonly etag?: string;
  readonly created?: boolean;
}
