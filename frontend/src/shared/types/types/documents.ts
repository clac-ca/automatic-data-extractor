import type { components } from "@types/api";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Readonly<Schemas[T]>;

export type DocumentStatus = Schemas["DocumentStatus"];

export type DocumentSource = Schemas["DocumentSource"];

export type UploaderSummary = Schema<"UploaderSummary">;

export type DocumentRecord = Schema<"DocumentRecord">;

export type DocumentListResponse = Schema<"DocumentListResponse">;
