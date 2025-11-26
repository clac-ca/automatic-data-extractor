import type { components } from "@schema";

export type ConfigurationPage = components["schemas"]["ConfigurationPage"];
export type ConfigurationRecord = components["schemas"]["ConfigurationRecord"];
export type ConfigurationVersionRecord = components["schemas"]["ConfigurationVersionRecord"];
export type ConfigurationScriptSummary = components["schemas"]["ConfigurationScriptSummary"];
export type ConfigurationScriptContent = components["schemas"]["ConfigurationScriptContent"];
export type ConfigurationVersionValidateResponse = components["schemas"]["ConfigurationVersionValidateResponse"];
export type ConfigurationVersionTestResponse = components["schemas"]["ConfigurationVersionTestResponse"];
export type ConfigurationValidateResponse = components["schemas"]["ConfigurationValidateResponse"];
export type ManifestResponse = components["schemas"]["ManifestResponse"];
export type ManifestPatchRequest = components["schemas"]["ManifestPatchRequest"];

export type ManifestEnvelope = ManifestResponse;
export interface ManifestEnvelopeWithEtag extends ManifestEnvelope {
  readonly etag?: string | null;
}

export type ConfigurationManifest = ManifestEnvelope["manifest"];

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
  readonly raw: ConfigurationManifest;
}

export type FileEntry = components["schemas"]["FileEntry"];
export type FileListing = components["schemas"]["FileListing"];
export type FileReadJson = components["schemas"]["FileReadJson"];
export type FileWriteResponse = components["schemas"]["FileWriteResponse"];
export type FileRenameResponse = components["schemas"]["FileRenameResponse"];
