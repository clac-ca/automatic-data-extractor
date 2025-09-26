/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />

import { screen } from "@testing-library/react";

import { App } from "../src/App";
import { renderWithProviders } from "./utils";

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("redirects unauthenticated users to the sign-in page", () => {
    renderWithProviders(<App />);

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeVisible();
  });
});
