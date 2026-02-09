import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  type AuthenticatedTopbarConfig,
  AuthenticatedTopbarProvider,
  useAuthenticatedTopbarConfig,
  useConfigureAuthenticatedTopbar,
} from "@/app/layouts/components/topbar/AuthenticatedTopbarContext";

function ConfigReader() {
  const config = useAuthenticatedTopbarConfig();
  return (
    <div>
      <span data-testid="desktop">{config?.desktopCenter ? "set" : "empty"}</span>
      <span data-testid="mobile">{config?.mobileAction ? "set" : "empty"}</span>
    </div>
  );
}

function ConfigWriter({ config }: { readonly config: AuthenticatedTopbarConfig | null }) {
  useConfigureAuthenticatedTopbar(config);
  return null;
}

describe("AuthenticatedTopbarContext", () => {
  it("registers, updates, and clears topbar config on unmount", () => {
    const configA: AuthenticatedTopbarConfig = {
      desktopCenter: <span>desktop-a</span>,
      mobileAction: <span>mobile-a</span>,
    };
    const configB: AuthenticatedTopbarConfig = {
      desktopCenter: <span>desktop-b</span>,
      mobileAction: <span>mobile-b</span>,
    };

    const { rerender, unmount } = render(
      <AuthenticatedTopbarProvider>
        <ConfigWriter config={configA} />
        <ConfigReader />
      </AuthenticatedTopbarProvider>,
    );

    expect(screen.getByTestId("desktop")).toHaveTextContent("set");
    expect(screen.getByTestId("mobile")).toHaveTextContent("set");

    rerender(
      <AuthenticatedTopbarProvider>
        <ConfigWriter config={configB} />
        <ConfigReader />
      </AuthenticatedTopbarProvider>,
    );

    expect(screen.getByTestId("desktop")).toHaveTextContent("set");
    expect(screen.getByTestId("mobile")).toHaveTextContent("set");

    rerender(
      <AuthenticatedTopbarProvider>
        <ConfigWriter config={null} />
        <ConfigReader />
      </AuthenticatedTopbarProvider>,
    );

    expect(screen.getByTestId("desktop")).toHaveTextContent("empty");
    expect(screen.getByTestId("mobile")).toHaveTextContent("empty");

    unmount();
  });

  it("is a safe no-op when configured without provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    function NoProviderWriter() {
      useConfigureAuthenticatedTopbar({
        desktopCenter: <span>desktop</span>,
        mobileAction: <span>mobile</span>,
      });
      return <div data-testid="ok">ok</div>;
    }

    render(<NoProviderWriter />);

    expect(screen.getByTestId("ok")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
