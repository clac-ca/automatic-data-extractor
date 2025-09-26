import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentUploadPanel } from "../src/features/documents/components/DocumentUploadPanel";
import { ToastProvider } from "../src/components/ToastProvider";

const mutateAsync = vi.fn();

vi.mock("../src/app/documents/hooks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/app/documents/hooks")>();
  return {
    ...actual,
    useUploadDocumentMutation: () => ({
      mutateAsync,
      isPending: false,
    }),
  };
});

describe("DocumentUploadPanel", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
  });

  function renderPanel() {
    return render(
      <ToastProvider>
        <DocumentUploadPanel
          workspaceId="workspace-1"
          documentType="invoice"
          configurations={[
            {
              configuration_id: "config-1",
              document_type: "invoice",
              title: "Default Config",
              version: 1,
              is_active: true,
              activated_at: null,
              payload: {},
              created_at: "2024-01-01T00:00:00Z",
              updated_at: "2024-01-01T00:00:00Z",
            },
          ]}
        />
      </ToastProvider>,
    );
  }

  it("uploads queued files with default configuration", async () => {
    const { container } = renderPanel();
    const fileInput = container.querySelector(
      "input[type='file']",
    ) as HTMLInputElement;
    const file = new File(["content"], "sample.csv", { type: "text/csv" });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: [file] },
      });
    });

    mutateAsync.mockResolvedValue({});

    const uploadButton = screen.getByRole("button", { name: /upload files/i });
    await act(async () => {
      fireEvent.click(uploadButton);
    });

    expect(mutateAsync).toHaveBeenCalledTimes(1);
    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        workspaceId: "workspace-1",
        file,
        options: expect.objectContaining({
          documentType: "invoice",
          metadata: {},
          configurationIds: ["config-1"],
        }),
      }),
    );
  });

  it("honours advanced configuration selections", async () => {
    const { container } = render(
      <ToastProvider>
        <DocumentUploadPanel
          workspaceId="workspace-1"
          documentType="invoice"
          configurations={[
            {
              configuration_id: "config-1",
              document_type: "invoice",
              title: "Default Config",
              version: 1,
              is_active: true,
              activated_at: null,
              payload: {},
              created_at: "2024-01-01T00:00:00Z",
              updated_at: "2024-01-01T00:00:00Z",
            },
            {
              configuration_id: "config-2",
              document_type: "invoice",
              title: "Experimental",
              version: 2,
              is_active: false,
              activated_at: null,
              payload: {},
              created_at: "2024-01-01T00:00:00Z",
              updated_at: "2024-01-01T00:00:00Z",
            },
          ]}
        />
      </ToastProvider>,
    );

    const fileInput = container.querySelector(
      "input[type='file']",
    ) as HTMLInputElement;
    const file = new File(["content"], "sample.csv", { type: "text/csv" });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: [file] },
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /advanced options/i }));

    const defaultCheckbox = screen.getByLabelText("Default Config (v1)");
    const experimentalCheckbox = screen.getByLabelText("Experimental (v2)");

    fireEvent.click(defaultCheckbox);
    fireEvent.click(experimentalCheckbox);

    mutateAsync.mockResolvedValue({});

    const uploadButton = screen.getByRole("button", { name: /upload files/i });
    await act(async () => {
      fireEvent.click(uploadButton);
    });

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({
          configurationIds: ["config-2"],
        }),
      }),
    );
  });
});
