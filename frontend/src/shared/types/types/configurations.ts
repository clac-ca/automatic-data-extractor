import type { components } from "@types/api";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Readonly<Schemas[T]>;

export type ConfigurationRecord = Schema<"ConfigurationRecord">;

export type ConfigurationColumn = Schema<"ConfigurationColumnOut">;

export type ConfigurationScriptVersion = Schema<"ConfigurationScriptVersionOut">;

export type ConfigurationCreatePayload = Schema<"ConfigurationCreate">;

export type ConfigurationColumnInput = Schema<"ConfigurationColumnIn">;

export type ConfigurationScriptVersionInput = Schema<"ConfigurationScriptVersionIn">;

export type ConfigurationColumnBindingUpdate = Schema<"ConfigurationColumnBindingUpdate">;
