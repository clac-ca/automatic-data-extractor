import { fireEvent, render, screen, waitFor } from "@/test/test-utils";
import { describe, expect, it, vi } from "vitest";

import { ApiError, buildApiErrorMessage, type ProblemDetails } from "@/api/errors";
import {
  ConfigurationImportDialog,
  type ConfigurationImportDialogMode,
  type ConfigurationImportSubmitPayload,
} from "../ConfigurationImportDialog";

function buildDialogProps(overrides: {
  mode?: ConfigurationImportDialogMode;
  isSubmitting?: boolean;
  canSubmit?: boolean;
  disabledReason?: string | null;
  hasUnsavedChanges?: boolean;
  onSubmit?: (payload: ConfigurationImportSubmitPayload) => Promise<void>;
  onError?: (message: string) => void;
} = {}) {
  return {
    open: true,
    mode: overrides.mode ?? "create",
    isSubmitting: overrides.isSubmitting ?? false,
    canSubmit: overrides.canSubmit ?? true,
    disabledReason: overrides.disabledReason ?? null,
    hasUnsavedChanges: overrides.hasUnsavedChanges ?? false,
    onClose: vi.fn(),
    onSubmit: overrides.onSubmit ?? vi.fn(async () => {}),
    onError: overrides.onError ?? vi.fn(),
  };
}

function setSelectedFile(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement | null;
  if (!input) {
    throw new Error("File input not found");
  }
  fireEvent.change(input, { target: { files: [file] } });
}

describe("ConfigurationImportDialog", () => {
  it("accepts zip files via drag and drop", async () => {
    const onSubmit = vi.fn(async () => {});
    const props = buildDialogProps({ onSubmit });
    const file = new File(["zip-data"], "config.zip", { type: "application/zip" });

    render(<ConfigurationImportDialog {...props} />);

    fireEvent.drop(screen.getByTestId("config-import-dropzone"), {
      dataTransfer: { files: [file] },
    });

    expect(screen.getByText("config.zip")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Import configuration" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
      expect(onSubmit).toHaveBeenCalledWith({ type: "zip", file });
    });
  });

  it("rejects non-zip files with inline guidance", () => {
    const file = new File(["plain-text"], "notes.txt", { type: "text/plain" });
    const props = buildDialogProps();

    render(<ConfigurationImportDialog {...props} />);

    fireEvent.drop(screen.getByTestId("config-import-dropzone"), {
      dataTransfer: { files: [file] },
    });

    expect(screen.getByText("Please choose a .zip archive.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Import configuration" })).toBeDisabled();
  });

  it("submits github URLs", async () => {
    const onSubmit = vi.fn(async () => {});
    const props = buildDialogProps({ onSubmit });

    render(<ConfigurationImportDialog {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "GitHub URL" }));
    fireEvent.change(screen.getByLabelText("GitHub repository URL"), {
      target: { value: "https://github.com/octo/repo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Import configuration" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
      expect(onSubmit).toHaveBeenCalledWith({
        type: "github",
        url: "https://github.com/octo/repo",
      });
    });
  });

  it("shows private repo fallback guidance for github imports", () => {
    const props = buildDialogProps();
    render(<ConfigurationImportDialog {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "GitHub URL" }));

    expect(screen.getByText(/Private repositories are not supported/i)).toBeInTheDocument();
    expect(screen.getByText(/GitHub Download ZIP/i)).toBeInTheDocument();
  });

  it("shows friendly file_too_large messages inline", async () => {
    const problem = {
      type: "bad_request",
      title: "Bad request",
      status: 400,
      instance: "/api/v1/workspaces/ws/configurations/import",
      detail: "logs/too_big.ndjson (limit=52428800)",
      errors: [{ message: "logs/too_big.ndjson", code: "file_too_large" }],
    } satisfies ProblemDetails;
    const onSubmit = vi.fn(async () => {
      throw new ApiError(buildApiErrorMessage(problem, 400), 400, problem);
    });

    const props = buildDialogProps({ onSubmit });
    const file = new File(["zip-data"], "config.zip", { type: "application/zip" });
    render(<ConfigurationImportDialog {...props} />);

    setSelectedFile(file);
    fireEvent.click(screen.getByRole("button", { name: "Import configuration" }));

    await waitFor(() => {
      expect(screen.getByText(/too large to import/i)).toBeInTheDocument();
    });
  });

  it("disables submit while upload is pending", () => {
    const file = new File(["zip-data"], "config.zip", { type: "application/zip" });
    const initialProps = buildDialogProps({ isSubmitting: false });
    const { rerender } = render(<ConfigurationImportDialog {...initialProps} />);

    setSelectedFile(file);

    const pendingProps = buildDialogProps({
      isSubmitting: true,
      onSubmit: initialProps.onSubmit,
      onError: initialProps.onError,
    });
    rerender(<ConfigurationImportDialog {...pendingProps} />);

    expect(screen.getByRole("button", { name: "Import configuration" })).toBeDisabled();
  });
});
