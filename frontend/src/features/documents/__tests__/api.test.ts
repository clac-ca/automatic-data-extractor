import { describe, expect, it } from "vitest";

import { buildDocumentsSearchParams } from "../api";

describe("buildDocumentsSearchParams", () => {
  it("serialises repeatable parameters for arrays", () => {
    const params = buildDocumentsSearchParams({
      status: ["uploaded", "processed"],
      tag: ["finance", "ops"],
      uploader_id: ["01H", "01J"],
      page: 2,
      per_page: 100,
      include_total: true,
    });

    expect(params.getAll("status")).toEqual(["uploaded", "processed"]);
    expect(params.getAll("tag")).toEqual(["finance", "ops"]);
    expect(params.getAll("uploader_id")).toEqual(["01H", "01J"]);
    expect(params.get("page")).toBe("2");
    expect(params.get("per_page")).toBe("100");
    expect(params.get("include_total")).toBe("true");
  });
});
