import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DocumentRecord } from "../../../../shared/types/documents";
import { uploadWorkspaceDocument } from "../../api";
import { useUploadDocumentsMutation } from "../useUploadDocumentsMutation";

vi.mock("../../api", () => ({
  uploadWorkspaceDocument: vi.fn(),
}));

describe("useUploadDocumentsMutation", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("uploads each file, reports progress, and refetches active queries", async () => {
    const files = [
      new File(["one"], "one.csv", { type: "text/csv" }),
      new File(["two"], "two.pdf", { type: "application/pdf" }),
    ];

    const mockedUpload = vi.mocked(uploadWorkspaceDocument);
    mockedUpload.mockImplementation(async (_workspaceId: string, { file }: { file: File }) => ({
      document_id: `doc-${file.name}`,
      workspace_id: "workspace-123",
      name: file.name,
      content_type: file.type,
      byte_size: file.size,
      metadata: {},
      status: "uploaded",
      source: "manual_upload",
      expires_at: new Date().toISOString(),
      last_run_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      deleted_at: null,
      deleted_by: null,
      tags: [],
      uploader: null,
    } as DocumentRecord));

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    function Wrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    }

    const { result } = renderHook(() => useUploadDocumentsMutation("workspace-123"), {
      wrapper: Wrapper,
    });

    const progressSpy = vi.fn();

    await act(async () => {
      await result.current.mutateAsync({ files, onProgress: progressSpy });
    });

    expect(mockedUpload).toHaveBeenCalledTimes(2);
    expect(mockedUpload).toHaveBeenNthCalledWith(1, "workspace-123", {
      expiresAt: undefined,
      file: files[0],
      metadata: undefined,
    });
    expect(mockedUpload).toHaveBeenNthCalledWith(2, "workspace-123", {
      expiresAt: undefined,
      file: files[1],
      metadata: undefined,
    });

    expect(progressSpy).toHaveBeenCalledTimes(2);
    expect(progressSpy).toHaveBeenNthCalledWith(1, {
      file: files[0],
      index: 0,
      total: 2,
    });
    expect(progressSpy).toHaveBeenNthCalledWith(2, {
      file: files[1],
      index: 1,
      total: 2,
    });

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["documents", "workspace-123", "list"],
        refetchType: "active",
      });
    });

    queryClient.clear();
  });
});
