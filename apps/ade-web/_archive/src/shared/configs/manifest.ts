import { z } from "zod";

import type { ConfigManifest, ParsedManifest, ManifestColumn, ManifestTableSection } from "./types";

const manifestColumnSchema = z
  .object({
    key: z.string(),
    label: z.string(),
    path: z.string(),
    ordinal: z.number().int(),
    required: z.boolean().optional(),
    enabled: z.boolean().optional(),
    depends_on: z.array(z.string()).optional(),
  })
  .transform((value) => ({
    ...value,
    depends_on: value.depends_on ?? [],
  }));

const tableEntrySchema = z
  .object({
    path: z.string(),
  })
  .strict();

const manifestSchema = z
  .object({
    name: z.string(),
    files_hash: z.string().default(""),
    columns: z.array(manifestColumnSchema).default([]),
    table: z
      .object({
        transform: tableEntrySchema.nullable().optional(),
        validators: tableEntrySchema.nullable().optional(),
      })
      .partial()
      .optional(),
  })
  .passthrough();

export function parseManifest(raw: ConfigManifest | null | undefined): ParsedManifest {
  if (!raw) {
    return {
      name: "",
      filesHash: "",
      columns: [],
      table: undefined,
      raw: {},
    };
  }

  const parsed = manifestSchema.safeParse(raw);
  if (!parsed.success) {
    console.warn("Unable to parse manifest payload", parsed.error);
    return {
      name: "",
      filesHash: "",
      columns: [],
      table: undefined,
      raw,
    };
  }

  const { name, files_hash: filesHash, columns, table, ...rest } = parsed.data;

  return {
    name,
    filesHash,
    columns: columns.map<ManifestColumn>((column) => ({
      key: column.key,
      label: column.label,
      path: column.path,
      ordinal: column.ordinal,
      required: column.required ?? false,
      enabled: column.enabled ?? true,
      depends_on: column.depends_on ?? [],
    })),
    table: table
      ? ({
          transform: table.transform ?? null,
          validators: table.validators ?? null,
        } satisfies ManifestTableSection)
      : undefined,
    raw: { ...rest, name, files_hash: filesHash, columns, table },
  };
}

export function composeManifestPatch(current: ParsedManifest, nextColumns: ManifestColumn[]): ConfigManifest {
  return {
    ...current.raw,
    name: current.name,
    files_hash: current.filesHash,
    columns: nextColumns.map((column) => ({
      key: column.key,
      label: column.label,
      path: column.path,
      ordinal: column.ordinal,
      required: column.required ?? false,
      enabled: column.enabled ?? true,
      depends_on: Array.from(column.depends_on ?? []),
    })),
    table: current.table
      ? {
          transform: current.table.transform ?? null,
          validators: current.table.validators ?? null,
        }
      : undefined,
  };
}
