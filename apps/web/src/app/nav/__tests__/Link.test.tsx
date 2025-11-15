import React from "react";
import userEvent from "@testing-library/user-event";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NavProvider, useLocation } from "../history";
import { Link, NavLink } from "../Link";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

describe("Link", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/initial");
  });

  it("navigates with the history helper when clicked", async () => {
    const user = userEvent.setup();
    render(
      <NavProvider>
        <>
          <Link to="/workspaces">Go to workspaces</Link>
          <LocationProbe />
        </>
      </NavProvider>,
    );

    await user.click(screen.getByRole("link", { name: "Go to workspaces" }));

    expect(screen.getByTestId("location")).toHaveTextContent("/workspaces");
  });

  it("leaves navigation to the browser when target is not _self", () => {
    const onClick = vi.fn((event: React.MouseEvent<HTMLAnchorElement>) => {
      expect(event.defaultPrevented).toBe(false);
      event.preventDefault();
    });
    render(
      <NavProvider>
        <>
          <Link to="/workspaces" target="_blank" onClick={onClick}>
            External nav
          </Link>
          <LocationProbe />
        </>
      </NavProvider>,
    );

    const anchor = screen.getByRole("link", { name: "External nav" });
    fireEvent.click(anchor, { button: 0 });

    expect(onClick).toHaveBeenCalled();
    expect(screen.getByTestId("location")).toHaveTextContent("/initial");
  });

  it("defaults rel when opening in a new tab", () => {
    render(
      <NavProvider>
        <>
          <Link
            to="/workspaces"
            target="_blank"
            onClick={(event) => {
              expect(event.defaultPrevented).toBe(false);
              event.preventDefault();
            }}
          >
            External nav
          </Link>
          <LocationProbe />
        </>
      </NavProvider>,
    );

    const anchor = screen.getByRole("link", { name: "External nav" });
    expect(anchor).toHaveAttribute("rel", "noopener noreferrer");

    fireEvent.click(anchor, { button: 0 });
    expect(screen.getByTestId("location")).toHaveTextContent("/initial");
  });

  it("lets the browser handle external URLs", () => {
    let prevented: boolean | null = null;

    render(
      <NavProvider>
        <>
          <Link
            to="https://example.com/docs"
            onClick={(event) => {
              prevented = event.defaultPrevented;
              event.preventDefault();
            }}
          >
            External docs
          </Link>
          <LocationProbe />
        </>
      </NavProvider>,
    );

    const anchor = screen.getByRole("link", { name: "External docs" });
    fireEvent.click(anchor, { button: 0 });

    expect(prevented).toBe(false);
    expect(screen.getByTestId("location")).toHaveTextContent("/initial");
  });

  it("respects download links", () => {
    let prevented: boolean | null = null;

    render(
      <NavProvider>
        <>
          <Link
            to="/files/report.csv"
            download
            onClick={(event) => {
              prevented = event.defaultPrevented;
              event.preventDefault();
            }}
          >
            Download report
          </Link>
          <LocationProbe />
        </>
      </NavProvider>,
    );

    const anchor = screen.getByRole("link", { name: "Download report" });
    fireEvent.click(anchor, { button: 0 });

    expect(prevented).toBe(false);
    expect(screen.getByTestId("location")).toHaveTextContent("/initial");
  });

  it("respects a provided rel", () => {
    const ref = React.createRef<HTMLAnchorElement>();
    render(
      <NavProvider>
        <Link ref={ref} to="/workspaces" target="_blank" rel="noopener">
          External nav
        </Link>
        <LocationProbe />
      </NavProvider>,
    );

    expect(ref.current?.rel).toBe("noopener");
  });
});

describe("NavLink", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/initial");
  });

  it("forwards click handlers", () => {
    const handleClick = vi.fn();
    render(
      <NavProvider>
        <NavLink to="/workspaces" onClick={handleClick}>
          Workspaces
        </NavLink>
      </NavProvider>,
    );

    const anchor = screen.getByRole("link", { name: "Workspaces" });
    fireEvent.click(anchor, { button: 0 });

    expect(handleClick).toHaveBeenCalled();
  });

  it("marks active links with aria-current", () => {
    render(
      <NavProvider>
        <NavLink to="/initial" end>
          Current page
        </NavLink>
      </NavProvider>,
    );

    expect(screen.getByRole("link", { name: "Current page" })).toHaveAttribute("aria-current", "page");
  });

  it("passes anchor attributes through to the Link primitive", () => {
    render(
      <NavProvider>
        <>
          <NavLink
            to="/workspaces"
            target="_blank"
            data-testid="workspace-link"
            onClick={(event) => {
              expect(event.defaultPrevented).toBe(false);
              event.preventDefault();
            }}
          >
            Workspaces
          </NavLink>
          <LocationProbe />
        </>
      </NavProvider>,
    );

    const anchor = screen.getByTestId("workspace-link");
    expect(anchor).toHaveAttribute("target", "_blank");
    expect(anchor).toHaveAttribute("rel", "noopener noreferrer");

    fireEvent.click(anchor, { button: 0 });
    expect(screen.getByTestId("location")).toHaveTextContent("/initial");
  });
});
