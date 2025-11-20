import type { components } from "@schema";

export type ConfigurationPage = components["schemas"]["ConfigurationPage"];
export type ConfigRecord = components["schemas"]["ConfigurationRecord"];
export interface ConfigVersionRecord {
  readonly config_version_id: string;
  readonly config_id: string;
  readonly workspace_id: string;
  readonly status: "draft" | "published" | "active" | "inactive";
  readonly semver?: string | null;
  readonly content_digest?: string | null;
  readonly created_at: string;
  readonly updated_at: string;
  readonly activated_at?: string | null;
  readonly deleted_at?: string | null;
}
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

export type FileEntry = components["schemas"]["FileEntry"];
export type FileListing = components["schemas"]["FileListing"];
export type FileReadJson = components["schemas"]["FileReadJson"];
export type FileWriteResponse = components["schemas"]["FileWriteResponse"];
export type FileRenameResponse = components["schemas"]["FileRenameResponse"];
