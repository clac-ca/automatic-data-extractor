import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentTypeRoute } from "./DocumentTypeRoute";
import type { WorkspaceProfile } from "../../../shared/api/types";
import { useDocumentTypeQuery } from "../hooks/useDocumentTypeQuery";

vi.mock("../hooks/useDocumentTypeQuery", () => ({
  useDocumentTypeQuery: vi.fn(),
}));

const mockUseDocumentTypeQuery = vi.mocked(useDocumentTypeQuery);

const workspace: WorkspaceProfile = {
  id: "workspace-1",
  name: "Finance",
  slug: "finance",
  roles: [],
  permissions: ["workspaces:read"],
  is_default: false,
};

describe("DocumentTypeRoute", () => {
  beforeEach(() => {
    mockUseDocumentTypeQuery.mockReturnValue({
      data: {
        id: "doctype-1",
        display_name: "Invoice ingestion",
        status: "active",
        last_run_at: "2025-02-01T12:00:00Z",
        success_rate_7d: 0.82,
        pending_jobs: 3,
        active_configuration_id: "config-1",
        configuration_summary: {
          version: 7,
          published_by: "jane.doe@example.com",
          published_at: "2025-01-31T09:15:00Z",
          draft: false,
          description: "Processes PDF invoices and extracts totals.",
          inputs: [
            { name: "file", type: "binary", required: true },
            { name: "locale", type: "string", required: false },
          ],
          revision_notes: "Updated parsing for new vendor format.",
        },
        alerts: ["Recent runs encountered validation warnings."],
      },
      isLoading: false,
      error: null,
    });
  });

  it("renders the document type summary", async () => {
    renderRoute();

    expect(await screen.findByRole("heading", { name: "Invoice ingestion" })).toBeInTheDocument();
    expect(screen.getByText("Workspace Finance")).toBeInTheDocument();
    expect(screen.getByText("82%", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Pending jobs")).toBeInTheDocument();
    expect(screen.getByText("Recent runs encountered validation warnings.")).toBeInTheDocument();
  });

  it("opens the configuration drawer when requested", async () => {
    const user = userEvent.setup();
    renderRoute();

    await user.click(await screen.findByRole("button", { name: /view full configuration/i }));

    const dialog = await screen.findByRole("dialog", { name: /configuration details/i });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("Updated parsing for new vendor format.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /close/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /configuration details/i })).not.toBeInTheDocument();
    });
  });

  it("allows the summary header action to open the configuration drawer", async () => {
    const user = userEvent.setup();
    renderRoute();

    await user.click(await screen.findByRole("button", { name: /review configuration details/i }));

    expect(await screen.findByRole("dialog", { name: /configuration details/i })).toBeInTheDocument();
  });
});

function renderRoute(overrides?: { workspace?: WorkspaceProfile | null }) {
  const contextWorkspace = overrides?.workspace ?? workspace;

  return render(
    <MemoryRouter initialEntries={["/workspaces/workspace-1/document-types/doctype-1"]}>
      <Routes>
        <Route element={<ContextOutlet workspace={contextWorkspace} />}>
          <Route path="/workspaces/:workspaceId/document-types/:documentTypeId" element={<DocumentTypeRoute />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

function ContextOutlet({ workspace }: { workspace: WorkspaceProfile | null }) {
  return <Outlet context={{ workspace }} />;
}
