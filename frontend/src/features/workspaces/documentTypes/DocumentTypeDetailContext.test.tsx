import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { DocumentTypeDetailResponse } from "../../../shared/api/types";
import { DocumentTypeDetailProvider, useDocumentTypeDetail } from "./DocumentTypeDetailContext";

const baseDocumentType: DocumentTypeDetailResponse = {
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
    inputs: [],
    revision_notes: null,
  },
  alerts: [],
};

function TestConsumer() {
  const { openConfigurationDrawer, closeConfigurationDrawer, isConfigurationDrawerOpen } = useDocumentTypeDetail();

  return (
    <div>
      <span data-testid="drawer-state">{isConfigurationDrawerOpen ? "open" : "closed"}</span>
      <button type="button" onClick={openConfigurationDrawer}>
        Open drawer
      </button>
      <button type="button" onClick={closeConfigurationDrawer}>
        Close drawer
      </button>
    </div>
  );
}

describe("DocumentTypeDetailProvider", () => {
  it("exposes open and close helpers for the configuration drawer", async () => {
    const user = userEvent.setup();

    render(
      <DocumentTypeDetailProvider documentType={baseDocumentType} workspaceName="Finance">
        <TestConsumer />
      </DocumentTypeDetailProvider>,
    );

    expect(screen.getByTestId("drawer-state")).toHaveTextContent("closed");

    await user.click(screen.getByRole("button", { name: /open drawer/i }));
    expect(screen.getByTestId("drawer-state")).toHaveTextContent("open");

    await user.click(screen.getByRole("button", { name: /close drawer/i }));
    expect(screen.getByTestId("drawer-state")).toHaveTextContent("closed");
  });

  it("resets the drawer state when the document type changes", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <DocumentTypeDetailProvider documentType={baseDocumentType} workspaceName="Finance">
        <TestConsumer />
      </DocumentTypeDetailProvider>,
    );

    await user.click(screen.getByRole("button", { name: /open drawer/i }));
    expect(screen.getByTestId("drawer-state")).toHaveTextContent("open");

    rerender(
      <DocumentTypeDetailProvider
        documentType={{ ...baseDocumentType, id: "doctype-2" }}
        workspaceName="Finance"
      >
        <TestConsumer />
      </DocumentTypeDetailProvider>,
    );

    expect(screen.getByTestId("drawer-state")).toHaveTextContent("closed");
  });
});
