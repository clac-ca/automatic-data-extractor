import type { ReactElement, ReactNode } from "react";
import { render as rtlRender, type RenderOptions } from "@testing-library/react";

import { NavProvider } from "@app/nav/history";

import { AppProviders } from "../app/AppProviders";

export * from "@testing-library/react";

interface AllProvidersProps {
  readonly children: ReactNode;
}

function AllProviders({ children }: AllProvidersProps) {
  return (
    <NavProvider>
      <AppProviders>{children}</AppProviders>
    </NavProvider>
  );
}

export function render(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return rtlRender(ui, { wrapper: AllProviders, ...options });
}
