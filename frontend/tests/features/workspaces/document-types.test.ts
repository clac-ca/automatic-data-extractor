import { describe, expect, it } from "vitest";

import type { ConfigurationRecord } from "@api/configurations";
import { mapConfigurationsToDocumentTypes } from "@features/workspaces/types";

let sequence = 0;

const makeConfiguration = (overrides: Partial<ConfigurationRecord>): ConfigurationRecord => ({
  configurationId: overrides.configurationId ?? `cfg-${sequence++}`,
  documentType: overrides.documentType ?? "invoice",
  title: overrides.title ?? "Invoice extraction",
  version: overrides.version ?? 1,
  isActive: overrides.isActive ?? true,
  activatedAt: overrides.activatedAt ?? new Date().toISOString(),
  payload: overrides.payload ?? {},
  createdAt: overrides.createdAt ?? new Date().toISOString(),
  updatedAt: overrides.updatedAt ?? new Date().toISOString()
});

describe("mapConfigurationsToDocumentTypes", () => {
  it("groups configurations by document type and prefers active versions", () => {
    const configurations = [
      makeConfiguration({ documentType: "invoice", isActive: false, version: 1 }),
      makeConfiguration({ documentType: "invoice", isActive: true, version: 2 }),
      makeConfiguration({ documentType: "statement", isActive: true, version: 1 })
    ];

    const result = mapConfigurationsToDocumentTypes(configurations);

    expect(result).toEqual([
      { id: "invoice", label: "invoice", isActive: true },
      { id: "statement", label: "statement", isActive: true }
    ]);
  });

  it("sorts options alphabetically", () => {
    const configurations = [
      makeConfiguration({ documentType: "z-type" }),
      makeConfiguration({ documentType: "a-type" })
    ];

    const result = mapConfigurationsToDocumentTypes(configurations);

    expect(result.map((option) => option.id)).toEqual(["a-type", "z-type"]);
  });
});
