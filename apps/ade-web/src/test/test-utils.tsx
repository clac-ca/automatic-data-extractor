import type { ReactElement, ReactNode } from "react";
import { render as rtlRender, type RenderOptions } from "@testing-library/react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { NuqsAdapter } from "nuqs/adapters/react-router/v7";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ThemeProvider } from "@components/providers/theme";
import { NotificationsProvider } from "@components/providers/notifications";

export * from "@testing-library/react";

interface AllProvidersProps {
  readonly children: ReactNode;
}

function TestAppProviders({ children }: AllProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
            staleTime: 0,
            gcTime: 0,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  useEffect(() => {
    return () => {
      queryClient.clear();
    };
  }, [queryClient]);

  return (
    <ThemeProvider>
      <NotificationsProvider>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </NotificationsProvider>
    </ThemeProvider>
  );
}

function AllProviders({ children }: AllProvidersProps) {
  return (
    <NuqsAdapter>
      <TestAppProviders>{children}</TestAppProviders>
    </NuqsAdapter>
  );
}

type RenderOptionsWithRoute = Omit<RenderOptions, "wrapper"> & {
  readonly route?: string;
};

export function render(ui: ReactElement, { route, ...options }: RenderOptionsWithRoute = {}) {
  if (route) {
    window.history.replaceState(null, "", route);
  }

  const router = createBrowserRouter([
    {
      path: "*",
      element: <AllProviders>{ui}</AllProviders>,
    },
  ]);

  return rtlRender(<RouterProvider router={router} />, options);
}

export { AllProviders };
