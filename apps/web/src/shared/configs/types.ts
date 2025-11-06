import type { components } from "@openapi";

export type ConfigRecord = components["schemas"]["ConfigRecord"];
export type ConfigVersionRecord = components["schemas"]["ConfigVersionRecord"];
export type ConfigScriptSummary = components["schemas"]["ConfigScriptSummary"];
export type ConfigScriptContent = components["schemas"]["ConfigScriptContent"];
export type ConfigVersionValidateResponse = components["schemas"]["ConfigVersionValidateResponse"];
export type ConfigVersionTestResponse = components["schemas"]["ConfigVersionTestResponse"];
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
