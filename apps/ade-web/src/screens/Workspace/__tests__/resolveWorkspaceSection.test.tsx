import { describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";

import { resolveWorkspaceSection } from "../index";

vi.mock("@screens/Workspace/sections/Overview", () => ({ default: () => <div>overview</div> }));
vi.mock("@screens/Workspace/sections/Documents", () => ({ default: () => <div>documents</div> }));
vi.mock("@screens/Workspace/sections/DocumentsV2", () => ({ default: () => <div>documents v2</div> }));
vi.mock("@screens/Workspace/sections/DocumentsV3", () => ({ default: () => <div>documents v3</div> }));
vi.mock("@screens/Workspace/sections/DocumentsV4", () => ({ default: () => <div>documents v4</div> }));
vi.mock("@screens/Workspace/sections/DocumentsV5", () => ({ default: () => <div>documents v5</div> }));
vi.mock("@screens/Workspace/sections/DocumentsV6", () => ({ default: () => <div>documents v6</div> }));
vi.mock("@screens/Workspace/sections/DocumentsV7", () => ({ default: () => <div>documents v7</div> }));
vi.mock("@screens/Workspace/sections/DocumentsV8", () => ({ default: () => <div>documents v8</div> }));
vi.mock("@screens/Workspace/sections/DocumentsV9", () => ({ default: () => <div>documents v9</div> }));
vi.mock("@screens/Workspace/sections/Documents/components/DocumentDetail", () => ({
  default: () => <div>document detail</div>,
}));
vi.mock("@screens/Workspace/sections/Runs", () => ({ default: () => <div>runs</div> }));
vi.mock("@screens/Workspace/sections/ConfigBuilder", () => ({ default: () => <div>configs</div> }));
vi.mock("@screens/Workspace/sections/ConfigBuilder/detail", () => ({
  default: () => <div>config detail</div>,
}));
vi.mock("@screens/Workspace/sections/ConfigBuilder/workbench", () => ({ default: () => <div>editor</div> }));
vi.mock("@screens/Workspace/sections/Settings", () => ({ default: () => <div>settings</div> }));
vi.mock("@ui/PageState", () => ({
  PageState: ({ title }: { title: string }) => <div>{title}</div>,
}));

describe("resolveWorkspaceSection", () => {
  const workspaceId = "ws-1";

  it("redirects to the default section when no segments are provided", () => {
    const result = resolveWorkspaceSection(workspaceId, [], "?foo=1", "#hash");
    expect(result).toEqual({
      kind: "redirect",
      to: "/workspaces/ws-1/documents?foo=1#hash",
    });
  });

  it("returns the documents detail section when a document id is present", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents", "doc-22"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents:doc-22" });
  });

  it("returns the documents v4 section for the documents-v4 slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents-v4"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents-v4", fullHeight: true });
  });

  it("returns the documents v2 section for the documents-v2 slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents-v2"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents-v2", fullHeight: true });
  });

  it("returns the documents v3 section for the documents-v3 slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents-v3"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents-v3", fullHeight: true });
  });

  it("returns the documents v5 section for the documents-v5 slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents-v5"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents-v5", fullHeight: true });
  });

  it("returns the documents v6 section for the documents-v6 slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents-v6"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents-v6", fullHeight: true });
  });

  it("returns the documents v7 section for the documents-v7 slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents-v7"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents-v7", fullHeight: true });
  });

  it("returns the documents v8 section for the documents-v8 slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents-v8"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents-v8", fullHeight: true });
  });

  it("returns the documents v9 section for the documents-v9 slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents-v9"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents-v9", fullHeight: true });
  });

  it("returns the config builder index and details", () => {
    const index = resolveWorkspaceSection(workspaceId, ["config-builder"], "", "");
    expect(index).toMatchObject({ kind: "content", key: "config-builder" });

    const detail = resolveWorkspaceSection(workspaceId, ["config-builder", "cfg-9"], "", "");
    expect(detail).toMatchObject({ kind: "content", key: "config-builder:cfg-9" });
  });

  it("returns the config editor without encoding search/hash in the key", () => {
    const editor = resolveWorkspaceSection(
      workspaceId,
      ["config-builder", "cfg-9", "editor"],
      "?tab=editor",
      "#panel",
    );
    expect(editor).toMatchObject({
      kind: "content",
      key: "config-builder:cfg-9:editor",
    });
  });

  it("returns the runs section for the runs slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["runs"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "runs" });
  });

  it("returns the settings section with trailing segments in the key", () => {
    const result = resolveWorkspaceSection(workspaceId, ["settings", "access", "roles"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "settings:access:roles" });
    if (result?.kind === "content") {
      const element = result.element as ReactElement<{ sectionSegments: string[] }>;
      expect(element.props.sectionSegments).toEqual(["access", "roles"]);
    }
  });

  it("defaults to general settings when no trailing segment is provided", () => {
    const result = resolveWorkspaceSection(workspaceId, ["settings"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "settings:general" });
    if (result?.kind === "content") {
      const element = result.element as ReactElement<{ sectionSegments: string[] }>;
      expect(element.props.sectionSegments).toEqual([]);
    }
  });
});
