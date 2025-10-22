/* eslint-disable react-refresh/only-export-components */
import type { ReactElement, ReactNode } from "react";
import { AppProviders } from "../app/AppProviders";
import { render as rtlRender, type RenderOptions } from "@testing-library/react";

interface AllProvidersProps {
  readonly children: ReactNode;
}

function AllProviders({ children }: AllProvidersProps) {
  return <AppProviders>{children}</AppProviders>;
}

export function render(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return rtlRender(ui, { wrapper: AllProviders, ...options });
}

export * from "@testing-library/react";
