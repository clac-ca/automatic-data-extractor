import { describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";

import { resolveWorkspaceSection } from "../index";

vi.mock("@screens/Workspace/sections/Overview", () => ({ default: () => <div>overview</div> }));
vi.mock("@screens/Workspace/sections/Documents", () => ({ default: () => <div>documents</div> }));
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
