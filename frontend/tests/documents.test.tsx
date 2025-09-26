/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />

import { act, fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";

import {
  useActiveConfigurationsQuery,
  useDeleteDocumentMutation,
  useUploadDocumentMutation,
  useWorkspaceDocumentsQuery,
} from "../src/app/documents/hooks";
import { ApiError } from "../src/api/errors";
import { WorkspaceDocumentsPage } from "../src/pages/WorkspaceDocumentsPage";
import {
  createTestQueryClient,
  createTestWrapper,
  renderWithProviders,
} from "./utils";

vi.mock("../src/app/auth/AuthContext", () => {
  const React = require("react");
  const stubValue = {
    status: "authenticated" as const,
    token: "test-token",
    email: "tester@example.com",
    error: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    clearError: vi.fn(),
  };

  return {
    AuthProvider: ({ children }: { children: React.ReactNode }) => (
      <React.Fragment>{children}</React.Fragment>
    ),
    useAuth: () => stubValue,
  };
});

describe("document hooks", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns documents when the API call succeeds", async () => {
    const payload = [
      {
        document_id: "doc-1",
        original_filename: "invoice.pdf",
        content_type: "application/pdf",
        byte_size: 2048,
        sha256: "abc123",
        stored_uri: "alpha/doc-1",
        metadata: { document_type: "invoice" },
        expires_at: "2024-05-01T00:00:00Z",
        created_at: "2024-04-01T00:00:00Z",
        updated_at: "2024-04-01T00:00:00Z",
        deleted_at: null,
        deleted_by: null,
        delete_reason: null,
      },
    ];

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));

    const { result } = renderHook(
      () => useWorkspaceDocumentsQuery("alpha", null),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/workspaces/alpha/documents"),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].documentType).toBe("invoice");
  });

  it("surfaces unauthorized errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
        statusText: "Unauthorized",
      }),
    );

    const queryClient = createTestQueryClient();
    const { result } = renderHook(
      () => useWorkspaceDocumentsQuery("alpha", null),
      { wrapper: createTestWrapper({ queryClient }) },
    );

    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiError));
    expect(queryClient.getQueryState(["workspaces", "alpha", "documents", "all"])?.error).toBeInstanceOf(ApiError);
  });

  it("returns active configurations", async () => {
    const payload = [
      {
        configuration_id: "cfg-1",
        document_type: "invoice",
        title: "Invoice v1",
        version: 1,
        is_active: true,
        activated_at: "2024-04-01T00:00:00Z",
        payload: {},
        created_at: "2024-03-01T00:00:00Z",
        updated_at: "2024-03-01T00:00:00Z",
      },
    ];

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );

    const { result } = renderHook(
      () => useActiveConfigurationsQuery("alpha"),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(payload);
  });

  it("uploads documents with the provided metadata", async () => {
    const payload = {
      document_id: "doc-1",
      original_filename: "invoice.pdf",
      content_type: "application/pdf",
      byte_size: 2048,
      sha256: "abc123",
      stored_uri: "alpha/doc-1",
      metadata: { document_type: "invoice" },
      expires_at: "2024-05-01T00:00:00Z",
      created_at: "2024-04-01T00:00:00Z",
      updated_at: "2024-04-01T00:00:00Z",
      deleted_at: null,
      deleted_by: null,
      delete_reason: null,
    };

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      if (url.includes("/documents")) {
        expect(init?.method).toBe("POST");
        expect(init?.body).toBeInstanceOf(FormData);
        return Promise.resolve(new Response(JSON.stringify(payload), { status: 201 }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    const { result } = renderHook(() => useUploadDocumentMutation(), {
      wrapper: createTestWrapper(),
    });

    const file = new File(["test"], "invoice.pdf", { type: "application/pdf" });

    await act(async () => {
      await result.current.mutateAsync({
        workspaceId: "alpha",
        file,
        options: {
          documentType: "invoice",
          metadata: { source: "tests" },
          expiresAt: "2024-05-01",
          configurationIds: ["cfg-1"],
        },
      });
    });

    expect(fetchMock).toHaveBeenCalled();
  });

  it("deletes documents using the API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      if (url.includes("/documents/")) {
        expect(init?.method).toBe("DELETE");
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    const { result } = renderHook(() => useDeleteDocumentMutation(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        workspaceId: "alpha",
        documentId: "doc-1",
      });
    });

    expect(fetchMock).toHaveBeenCalled();
  });
});

describe("WorkspaceDocumentsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("queues files via drag and drop and uploads them", async () => {
    const file = new File(["test"], "invoice.pdf", { type: "application/pdf" });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      if (url.endsWith("/workspaces")) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                workspace_id: "alpha",
                name: "Alpha",
                slug: "alpha",
                role: "OWNER",
                permissions: ["workspace:read"],
                is_default: true,
              },
            ]),
            { status: 200 },
          ),
        );
      }
      if (url.endsWith("/workspaces/alpha")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              workspace: {
                workspace_id: "alpha",
                name: "Alpha",
                slug: "alpha",
                role: "OWNER",
                permissions: ["workspace:read"],
                is_default: true,
              },
            }),
            { status: 200 },
          ),
        );
      }
      if (url.endsWith("/documents")) {
        if (init?.method === "GET") {
          return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
        }
        if (init?.method === "POST") {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                document_id: "doc-1",
                original_filename: file.name,
                content_type: file.type,
                byte_size: file.size,
                sha256: "abc123",
                stored_uri: "alpha/doc-1",
                metadata: { document_type: "invoice" },
                expires_at: "2024-05-01T00:00:00Z",
                created_at: "2024-04-01T00:00:00Z",
                updated_at: "2024-04-01T00:00:00Z",
                deleted_at: null,
                deleted_by: null,
                delete_reason: null,
              }),
              { status: 201 },
            ),
          );
        }
      }
      if (url.endsWith("/configurations/active")) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                configuration_id: "cfg-1",
                document_type: "invoice",
                title: "Invoice",
                version: 1,
                is_active: true,
                activated_at: "2024-04-01T00:00:00Z",
                payload: {},
                created_at: "2024-03-01T00:00:00Z",
                updated_at: "2024-03-01T00:00:00Z",
              },
            ]),
            { status: 200 },
          ),
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(
      <Routes>
        <Route path="/workspaces/:workspaceId/documents" element={<WorkspaceDocumentsPage />} />
      </Routes>,
      {
        route: "/workspaces/alpha/documents",
      },
    );

    await waitFor(() => expect(screen.getByLabelText("Document type")).toBeInTheDocument());
    const documentTypeSelect = screen.getByLabelText("Document type") as HTMLSelectElement;
    await waitFor(() => expect(documentTypeSelect.value).toBe("invoice"));

    const dropLabel = screen.getByText(/Drag and drop files here/i).closest("label");
    expect(dropLabel).not.toBeNull();

    const dataTransfer = {
      files: [file],
      items: [{ kind: "file", type: file.type, getAsFile: () => file }],
      types: ["Files"],
      dropEffect: "copy",
      effectAllowed: "all",
    } as unknown as DataTransfer;

    act(() => {
      fireEvent.dragOver(dropLabel!, { dataTransfer });
      fireEvent.drop(dropLabel!, { dataTransfer });
    });

    await screen.findByText(file.name);

    const uploadButton = screen.getByRole("button", { name: /upload files/i });
    await act(async () => {
      await userEvent.click(uploadButton);
    });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/workspaces/alpha/documents"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });
});
