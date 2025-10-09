import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { RequirePermission } from "./RequirePermission";
import { AccessDenied } from "./AccessDenied";

const useOutletContextMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => useOutletContextMock(),
  };
});

describe("RequirePermission", () => {
  beforeEach(() => {
    useOutletContextMock.mockReset();
  });

  it("renders children when the workspace has at least one required permission", () => {
    useOutletContextMock.mockReturnValue({ workspace: { permissions: ["Workspace.Members.Read"] } });

    render(
      <RequirePermission needed={["Workspace.Members.Read", "Workspace.Members.ReadWrite"]}>
        <div>allowed</div>
      </RequirePermission>,
    );

    expect(screen.getByText("allowed")).toBeInTheDocument();
  });

  it("renders the fallback when permissions are missing", () => {
    useOutletContextMock.mockReturnValue({ workspace: { permissions: [] } });

    render(
      <RequirePermission
        needed={["Workspace.Settings.ReadWrite"]}
        fallback={<AccessDenied>You do not have permission.</AccessDenied>}
      >
        <div>allowed</div>
      </RequirePermission>,
    );

    expect(screen.getByText(/you do not have permission\./i)).toBeInTheDocument();
    expect(screen.queryByText("allowed")).not.toBeInTheDocument();
  });

  it("requires all permissions when mode is set to all", () => {
    useOutletContextMock.mockReturnValue({ workspace: { permissions: ["Workspace.Members.Read"] } });

    render(
      <RequirePermission
        needed={["Workspace.Members.Read", "Workspace.Members.ReadWrite"]}
        mode="all"
        fallback={<div>no access</div>}
      >
        <div>allowed</div>
      </RequirePermission>,
    );

    expect(screen.getByText("no access")).toBeInTheDocument();
    expect(screen.queryByText("allowed")).not.toBeInTheDocument();
  });
});
