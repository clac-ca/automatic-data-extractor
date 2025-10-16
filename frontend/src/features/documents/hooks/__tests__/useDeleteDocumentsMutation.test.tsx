import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteWorkspaceDocuments } from "../../api";
import { useDeleteDocumentsMutation } from "../useDeleteDocumentsMutation";

vi.mock("../../api", () => ({
  deleteWorkspaceDocuments: vi.fn(),
}));

describe("useDeleteDocumentsMutation", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("calls the API and refetches active queries", async () => {
    const mockedDelete = vi.mocked(deleteWorkspaceDocuments);
    mockedDelete.mockResolvedValue(undefined);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    function Wrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    }

    const { result } = renderHook(() => useDeleteDocumentsMutation("workspace-456"), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync(["doc-1", "doc-2"]);
    });

    expect(mockedDelete).toHaveBeenCalledWith("workspace-456", ["doc-1", "doc-2"]);

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["documents", "workspace-456", "list"],
        refetchType: "active",
      });
    });

    queryClient.clear();
  });
});
