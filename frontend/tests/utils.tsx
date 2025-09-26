import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AuthProvider } from "../src/app/auth/AuthContext";
import { WorkspaceSelectionProvider } from "../src/app/workspaces/WorkspaceSelectionContext";
import { ToastProvider } from "../src/components/ToastProvider";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

interface ProviderOptions {
  route?: string;
  queryClient?: QueryClient;
}

export function createTestWrapper(options: ProviderOptions = {}) {
  const { route = "/", queryClient = createTestQueryClient() } = options;
  return function TestProviders({ children }: { children: ReactNode }) {
    return (
      <ToastProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <WorkspaceSelectionProvider>
              <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
            </WorkspaceSelectionProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ToastProvider>
    );
  };
}

export function renderWithProviders(
  ui: ReactElement,
  options: ProviderOptions = {},
) {
  const queryClient = options.queryClient ?? createTestQueryClient();
  const wrapper = createTestWrapper({ ...options, queryClient });
  return {
    queryClient,
    ...render(ui, { wrapper }),
  };
}
