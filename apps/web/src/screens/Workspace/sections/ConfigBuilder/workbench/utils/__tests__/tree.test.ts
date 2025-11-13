import { describe, expect, it } from "vitest";

import { createWorkbenchTreeFromListing } from "../tree";

import type { FileListing } from "@shared/configs/types";

const ISO = "2024-01-01T00:00:00.000Z";

function createListing(): FileListing {
  return {
    workspace_id: "workspace-1",
    config_id: "config-1",
    status: "active" as FileListing["status"],
    capabilities: { editable: true, can_create: true, can_delete: true, can_rename: true },
    root: "ade_config",
    prefix: "",
    depth: "infinity",
    generated_at: ISO,
    fileset_hash: "hash",
    summary: { files: 2, directories: 2 },
    limits: { code_max_bytes: 1024, asset_max_bytes: 2048 },
    count: 4,
    next_token: null,
    entries: [
      {
        path: "ade_config",
        name: "ade_config",
        parent: "",
        kind: "dir",
        depth: 0,
        size: null,
        mtime: ISO,
        etag: "root",
        content_type: "inode/directory",
        has_children: true,
      },
      {
        path: "ade_config/manifest.json",
        name: "manifest.json",
        parent: "ade_config",
        kind: "file",
        depth: 1,
        size: 100,
        mtime: ISO,
        etag: "manifest",
        content_type: "application/json",
        has_children: false,
      },
      {
        path: "ade_config/hooks",
        name: "hooks",
        parent: "ade_config",
        kind: "dir",
        depth: 1,
        size: null,
        mtime: ISO,
        etag: "hooks",
        content_type: "inode/directory",
        has_children: true,
      },
      {
        path: "ade_config/hooks/normalize.py",
        name: "normalize.py",
        parent: "ade_config/hooks",
        kind: "file",
        depth: 2,
        size: 120,
        mtime: ISO,
        etag: "normalize",
        content_type: "text/x-python",
        has_children: false,
      },
    ],
  };
}

describe("createWorkbenchTreeFromListing", () => {
  it("builds a nested tree with inferred languages", () => {
    const listing = createListing();
    const tree = createWorkbenchTreeFromListing(listing);

    expect(tree).not.toBeNull();
    expect(tree?.id).toBe("ade_config");
    expect(tree?.children?.map((node) => node.name)).toEqual(["hooks", "manifest.json"]);

    const hooks = tree?.children?.find((node) => node.name === "hooks");
    expect(hooks?.kind).toBe("folder");
    expect(hooks?.children?.[0]?.name).toBe("normalize.py");
    expect(hooks?.children?.[0]?.language).toBe("python");
    expect(hooks?.children?.[0]?.metadata).toEqual({
      size: 120,
      modifiedAt: ISO,
      contentType: "text/x-python",
      etag: "normalize",
    });

    const manifest = tree?.children?.find((node) => node.name === "manifest.json");
    expect(manifest?.language).toBe("json");
    expect(manifest?.metadata).toEqual({
      size: 100,
      modifiedAt: ISO,
      contentType: "application/json",
      etag: "manifest",
    });
  });
});
