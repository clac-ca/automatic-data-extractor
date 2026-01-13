import type { ReactElement, ReactNode } from "react";
import { render as rtlRender, type RenderOptions } from "@testing-library/react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { NuqsAdapter } from "nuqs/adapters/react-router/v7";

import { AppProviders } from "@app/providers/AppProviders";

export * from "@testing-library/react";

interface AllProvidersProps {
  readonly children: ReactNode;
}

function AllProviders({ children }: AllProvidersProps) {
  return (
    <NuqsAdapter>
      <AppProviders>{children}</AppProviders>
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
