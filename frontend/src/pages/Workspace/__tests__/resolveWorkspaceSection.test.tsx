import { describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";

import { resolveWorkspaceSection } from "../sectionResolver";

vi.mock("@/pages/Workspace/sections/Documents", () => ({
  default: () => <div>documents</div>,
  DocumentsDetailPage: ({ documentId }: { documentId: string }) => <div>doc {documentId}</div>,
}));
vi.mock("@/pages/Workspace/sections/Runs", () => ({ default: () => <div>runs</div> }));
vi.mock("@/pages/Workspace/sections/ConfigurationEditor", () => ({ default: () => <div>configs</div> }));
vi.mock("@/pages/Workspace/sections/ConfigurationEditor/workbench", () => ({ default: () => <div>editor</div> }));
vi.mock("@/pages/Workspace/sections/Settings", () => ({ default: () => <div>settings</div> }));
vi.mock("@/components/layout", () => ({
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

  it("returns the document detail page when a document id is present", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents", "doc-22"], "", "");
    expect(result).toMatchObject({
      kind: "content",
      key: "documents:doc-22",
      fullWidth: true,
      fullHeight: true,
    });
  });

  it("returns the documents section for the documents slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["documents"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "documents", fullWidth: true });
  });

  it("returns the configuration editor entry route and editor route", () => {
    const index = resolveWorkspaceSection(workspaceId, ["configurations"], "", "");
    expect(index).toMatchObject({ kind: "content", key: "configurations", fullHeight: true });

    const detail = resolveWorkspaceSection(workspaceId, ["configurations", "cfg-9"], "", "");
    expect(detail).toMatchObject({ kind: "content", key: "configurations:cfg-9", fullHeight: true });
  });

  it("rejects unknown trailing configuration segments", () => {
    const editor = resolveWorkspaceSection(
      workspaceId,
      ["configurations", "cfg-9", "editor"],
      "?tab=editor",
      "#panel",
    );
    expect(editor).toMatchObject({
      kind: "content",
      key: "not-found:configurations/cfg-9/editor",
    });
  });

  it("returns the runs section for the runs slug", () => {
    const result = resolveWorkspaceSection(workspaceId, ["runs"], "", "");
    expect(result).toMatchObject({ kind: "content", key: "runs", fullWidth: true });
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
