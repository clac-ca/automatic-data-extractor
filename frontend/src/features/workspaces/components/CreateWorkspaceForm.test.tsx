import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CreateWorkspaceForm } from "./CreateWorkspaceForm";
import { ApiError } from "../../../shared/api/client";
import type { WorkspaceProfile } from "../../../shared/api/types";

const mutateAsync = vi.fn();

vi.mock("../hooks/useCreateWorkspaceMutation", () => ({
  useCreateWorkspaceMutation: () => ({ mutateAsync, isPending: false }),
}));

describe("CreateWorkspaceForm", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
  });

  it("submits the workspace name", async () => {
    const user = userEvent.setup();
    const createdWorkspace: WorkspaceProfile = {
      id: "workspace-1",
      name: "Finance",
      slug: "finance",
      roles: ["workspace-owner"],
      permissions: ["Workspace.Members.ReadWrite"],
      is_default: false,
    };
    mutateAsync.mockResolvedValueOnce(createdWorkspace);
    const onCreated = vi.fn();

    render(<CreateWorkspaceForm onCreated={onCreated} />);

    await user.type(screen.getByLabelText(/workspace name/i), "  Finance  ");
    await user.click(screen.getByRole("button", { name: /create workspace/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({ name: "Finance" });
      expect(onCreated).toHaveBeenCalledWith(createdWorkspace);
    });
  });

  it("requires a name", async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();

    render(<CreateWorkspaceForm onCreated={onCreated} />);

    await user.click(screen.getByRole("button", { name: /create workspace/i }));

    expect(await screen.findByText(/enter a workspace name/i)).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("shows API errors", async () => {
    const user = userEvent.setup();
    const error = new ApiError("Invalid", 400, { detail: "Workspace name already exists" });
    mutateAsync.mockRejectedValueOnce(error);

    render(<CreateWorkspaceForm onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText(/workspace name/i), "Finance");
    await user.click(screen.getByRole("button", { name: /create workspace/i }));

    expect(await screen.findByText(/workspace name already exists/i)).toBeInTheDocument();
  });

  it("clears validation errors when the name changes", async () => {
    const user = userEvent.setup();
    render(<CreateWorkspaceForm onCreated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /create workspace/i }));
    expect(await screen.findByText(/enter a workspace name/i)).toBeInTheDocument();

    await user.type(screen.getByLabelText(/workspace name/i), "Finance");
    expect(screen.queryByText(/enter a workspace name/i)).not.toBeInTheDocument();
  });
});
