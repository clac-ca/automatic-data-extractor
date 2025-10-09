import type { ComponentProps } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { RequirePermission } from "./RequirePermission";

const useOutletContextMock = vi.fn();
const useParamsMock = vi.fn();
const navigatePropsMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => useOutletContextMock(),
    useParams: () => useParamsMock(),
    Navigate: (props: ComponentProps<typeof actual.Navigate>) => {
      navigatePropsMock(props);
      return <div data-testid="redirect" />;
    },
  };
});

describe("RequirePermission", () => {
  beforeEach(() => {
    useOutletContextMock.mockReset();
    useParamsMock.mockReset();
    navigatePropsMock.mockReset();
  });

  it("renders children when the workspace has at least one required permission", () => {
    useParamsMock.mockReturnValue({ workspaceId: "workspace-1" });
    useOutletContextMock.mockReturnValue({ workspace: { permissions: ["Workspace.Members.Read"] } });

    render(<RequirePermission needed="Workspace.Members.Read">{<div>allowed</div>}</RequirePermission>);

    expect(screen.getByText("allowed")).toBeInTheDocument();
    expect(navigatePropsMock).not.toHaveBeenCalled();
  });

  it("redirects to the workspace overview when permissions are missing", () => {
    useParamsMock.mockReturnValue({ workspaceId: "workspace-2" });
    useOutletContextMock.mockReturnValue({ workspace: { permissions: [] } });

    render(<RequirePermission needed="Workspace.Settings.ReadWrite">{<div>allowed</div>}</RequirePermission>);

    expect(screen.getByTestId("redirect")).toBeInTheDocument();
    expect(navigatePropsMock).toHaveBeenCalledWith(
      expect.objectContaining({ to: "/workspaces/workspace-2", replace: true }),
    );
    expect(screen.queryByText("allowed")).not.toBeInTheDocument();
  });

  it("falls back to the workspace list when no workspace id is present", () => {
    useParamsMock.mockReturnValue({});
    useOutletContextMock.mockReturnValue({ workspace: { permissions: [] } });

    render(<RequirePermission needed="Workspace.Settings.ReadWrite">{<div>allowed</div>}</RequirePermission>);

    expect(navigatePropsMock).toHaveBeenCalledWith(
      expect.objectContaining({ to: "/workspaces", replace: true }),
    );
  });
});
